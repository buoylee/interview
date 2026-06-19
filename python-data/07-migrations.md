# 07 · 迁移与 schema 演进

> **为什么这章重要**:模型(`models.py`)改了,数据库的表结构不会自己跟着变——你需要**迁移**把变更**版本化**地、可重放地应用到每个环境。更难的是线上:一张亿行表加个列、改个类型,做不好就是一次锁表停服。这章讲 Alembic 怎么用、autogenerate 能信到哪、以及**不停机改表**的套路。
>
> **一句话心智**:迁移是「schema 的 git」——每次变更一个带 `upgrade`/`downgrade` 的版本,顺着链往前推;线上改表要**先兼容、再清理**,拆成多次部署。

## 一、Alembic:SQLAlchemy 的迁移工具

Alembic 把每次 schema 变更存成一个**版本脚本**,串成一条链(每个记着 `down_revision = 上一个`):

```bash
alembic init alembic            # 初始化(生成 alembic.ini + alembic/ 目录)
# 配好 alembic/env.py 里的 target_metadata = Base.metadata 和数据库 URL 后:
alembic revision --autogenerate -m "add books.isbn"   # 对比模型与库,生成迁移
alembic upgrade head            # 应用到最新
alembic downgrade -1            # 回退一个版本
```

一个版本脚本长这样:

```python
# alembic/versions/3f2a..._add_books_isbn.py
revision = "3f2a..."
down_revision = "9c1b..."        # 指向上一个版本,构成链

def upgrade():
    op.add_column("books", sa.Column("isbn", sa.String(20), nullable=True))

def downgrade():
    op.drop_column("books", "isbn")
```

`upgrade` 往前、`downgrade` 往后。**迁移脚本要提交进 git**——它和代码一起版本化,CI/CD 里 `alembic upgrade head` 把每个环境推到一致。

## 二、autogenerate 能信到哪(边界很重要)

`--autogenerate` 对比「模型 `Base.metadata`」和「数据库当前结构」,**猜**出差异生成迁移。它很方便,但**不是全自动**,边界必须心里有数:

**能可靠测出**:加表 / 删表、加列 / 删列、加索引 / 唯一约束、(多数)列可空性变化。

**测不准 / 测不出**(需你手写或核对):

- **改列名**:autogenerate 看到的是「删了旧列 + 加了新列」——会生成 `drop_column + add_column`,**数据全丢**!改名要手写 `op.alter_column(..., new_column_name=...)`。
- **改类型**:能发现类型变了,但**数据怎么转换**它不管(`VARCHAR` → `INT` 要你写转换逻辑)。
- **数据迁移**:把数据从旧结构搬到新结构(填充新列、拆表),autogenerate 完全不碰,要手写 `op.execute(...)`。
- **表/列改名 vs 删加**的语义,它分不清你的意图。

**铁律**:**autogenerate 生成的每个迁移都要人 review 一遍再提交**——尤其留意有没有意料之外的 `drop_column`(往往是「改名被误判成删加」)。把它当「帮你起草」,不是「替你决定」。

```python
# 手写数据迁移的典型:加列后回填,再设非空
def upgrade():
    op.add_column("books", sa.Column("slug", sa.String(200), nullable=True))
    op.execute("UPDATE books SET slug = lower(replace(title, ' ', '-'))")  # 回填
    op.alter_column("books", "slug", nullable=False)                       # 再收紧
```

> **实测**(`lab/alembic/`,env.py 接到 `models.Base.metadata`)。空库上 `alembic revision --autogenerate`:
> ```
> Detected added table 'accounts'
> Detected added table 'authors'
> Detected added table 'books'
> Generating .../versions/8b46a381d163_initial_schema.py ... done
> ```
> 生成的 `upgrade()` 是正确的 `op.create_table(...)`,且**外键被识别**(`ForeignKeyConstraint(['author_id'], ['authors.id'])`)。`alembic upgrade head` 后 `alembic current` → `8b46a381d163 (head)`,`alembic_version` 表记录版本。**加表/列/外键 autogenerate 测得准**;改名/类型转换/数据迁移测不准(上面那几条),要手写。lab 里能自己跑一遍验证。

## 三、zero-downtime:线上改表的套路

线上大表的 DDL 可能**锁表**,几秒到几分钟,期间服务读写全卡。原则:**任何一次部署,新旧代码要能同时跑在同一个 schema 上**(因为滚动发布期间两版本并存)。于是危险变更都拆成**多次部署、每步都兼容**。

**加列**(安全,但别图省事):

- 加 `nullable=True` 或带默认值的列——安全,旧代码忽略它、新代码用它。
- ⚠️ 直接加 `NOT NULL` 且无默认值:旧代码的 INSERT 不带这列会失败。要么先可空回填再收紧(上面的三步),要么给默认值。

**改列 / 改类型**(危险,扩-迁-缩三步,跨多次部署):

1. **扩**:加一个新列(新类型),代码**双写**(同时写新旧列)。
2. **迁**:后台批量把存量数据从旧列搬到新列。
3. **缩**:代码切到只读写新列,确认无误后,再一次部署删掉旧列。

**加索引**(大表上 `CREATE INDEX` 会锁写):用 Postgres 的 `CONCURRENTLY`,它不锁写、在后台建:

```python
def upgrade():
    # CREATE INDEX CONCURRENTLY 不能在事务里跑,Alembic 要关掉这步的事务包裹
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_books_author_id", "books", ["author_id"],
            postgresql_concurrently=True,
        )
```

> 注意 `CONCURRENTLY` 必须在事务外执行,Alembic 默认把每个迁移包在事务里,所以要用 `autocommit_block()`(或在 env 里配 `transaction_per_migration` 并单独处理)。

## 四、迁移和部署,谁先谁后?

取决于变更**兼容性**,核心仍是「滚动发布期间新旧代码并存」:

- **向后兼容的变更(加可空列、加表)**:**先迁移、后发代码**。旧代码无视新列照常跑,新代码部署后即可用。
- **破坏性变更(删列、改名)**:**绝不能一步到位**。必须走「扩-迁-缩」,把破坏性的那一步(删旧列)推到**所有实例都已是新代码之后**的单独一次部署。
- 一句话:**让数据库的每个中间状态,都能被「正在运行的所有代码版本」接受**。

## Java/Go 对照框

| 关注点 | Java | Go | Python |
|---|---|---|---|
| 迁移工具 | Flyway / Liquibase | golang-migrate / goose / atlas | **Alembic** |
| 迁移形式 | SQL 文件 / XML changelog | SQL 文件对(up/down) | Python 脚本(`upgrade`/`downgrade`) |
| 从模型自动生成 | Hibernate `hbm2ddl`(不建议生产) | ent / atlas 可 diff | **autogenerate**(需 review) |
| 版本链 | 版本号顺序 | 文件序号 | `down_revision` 链 |

对照:**Alembic ≈ Flyway/Liquibase**,但迁移脚本是 Python(能写任意逻辑做数据迁移),比纯 SQL 的 Flyway 灵活。autogenerate 类似 Hibernate 的自动 DDL,但 Alembic 让你**先生成再 review 提交**,而非运行时自动改表(后者生产大忌)——这点更稳。zero-downtime 的「扩-迁-缩」套路是跨语言通用的,和工具无关。

## 章末面试卡

**Q1. 数据库迁移是什么?为什么不能让 ORM 自动建表就好?**
迁移是把 schema 变更版本化(每个版本带 upgrade/downgrade、串成链),可重放地应用到各环境并提交进 git。生产不用「ORM 自动建/改表」是因为它不可控、不可审计、改类型/改名会丢数据,也无法做 zero-downtime;迁移让每次变更可 review、可回退、可按部署顺序编排。

**Q2. autogenerate 能可靠测出什么?测不出什么?**
可靠:加/删表、加/删列、加索引/约束、多数可空性变化。测不准:改列名(会误判成删列+加列,丢数据)、改类型的数据转换、任何数据迁移——这些要手写,且每个 autogenerate 迁移都要人 review(尤其防意外的 drop_column)。

**Q3. 怎么不停机给大表加索引 / 改列?**
加索引用 `CREATE INDEX CONCURRENTLY`(不锁写、后台建,Alembic 里 `postgresql_concurrently=True` + `autocommit_block()`,因为它不能在事务里)。改列用「扩-迁-缩」三步跨多次部署:加新列双写 → 后台迁移存量 → 切只用新列后再删旧列。

**Q4. 迁移和部署谁先?**
看兼容性,原则是滚动发布期间新旧代码并存、数据库每个中间状态都被所有运行中的代码接受。向后兼容(加可空列/表):先迁移后发代码。破坏性(删列/改名):必须走扩-迁-缩,把删旧列推到所有实例都已更新为新代码之后的单独部署。
