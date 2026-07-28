shell.options.useWizards = false;
const user = os.getenv('MYSQL_CLUSTER_ADMIN') || 'icadmin';
const password = os.getenv('MYSQL_CLUSTER_ADMIN_PASSWORD') || 'ha-cluster';
const target = os.getenv('MYSQL_TARGET_MEMBER') || 'db2';
shell.connect({scheme: 'mysql', user, password, host: os.getenv('MYSQL_SEED') || 'db1', port: 3306});
const cluster = dba.getCluster('haLabCluster');
cluster.setPrimaryInstance(`${user}@${target}:3306`);
print(JSON.stringify(cluster.status({extended: 1}), null, 2));
