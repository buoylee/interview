"""一次性把 sklearn 的 california housing 导出成本地 CSV(之后完全离线)。
首次运行需要网络(sklearn 会下载并缓存数据集)。"""
from pathlib import Path

from sklearn.datasets import fetch_california_housing


def main():
    data = fetch_california_housing(as_frame=True)
    df = data.frame  # 含 8 个特征 + 目标列 MedHouseVal
    out = Path(__file__).parent / "data" / "california_housing.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)
    print(f"wrote {out} ({len(df)} rows, {df.shape[1]} cols)")


if __name__ == "__main__":
    main()
