# modify/filter_berlin.py
import pandas as pd
from utils.db import get_db_connection

QUERY = """
SELECT 
    a.uuid              AS uuid,
    b.uuid              AS relation_uuid,
    a.orig_id_x         AS orig_id,
    b.orig_id_x         AS relation_orig_id,
    a.heading           AS h_1,
    b.heading           AS h_2,
    a.comp_lon          AS lon_1,
    b.comp_lon          AS lon_2,
    a.comp_lat          AS lat_1,
    b.comp_lat          AS lat_2,
    a.source_x          AS source
FROM singapore a
JOIN singapore b
  ON a.uuid < b.uuid
 AND (a.geometry_comp_32648 <-> b.geometry_comp_32648) <= 0.5
 AND LEAST(ABS(a.heading - b.heading), 360 - ABS(a.heading - b.heading)) <= 20
"""

def run_query() -> pd.DataFrame:
    """Return edge list (and extras) from the DB. Coerce orig_id columns to nullable Int64."""
    engine = get_db_connection()
    with engine.connect() as conn:
        df = pd.read_sql_query(QUERY, conn)
    for c in ("orig_id", "relation_orig_id"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    return df

class UnionFind:
    def __init__(self):
        self.parent = {}
        self.rank = {}

    def find(self, x):
        p = self.parent.get(x, x)
        if p != x:
            self.parent[x] = self.find(p)
            return self.parent[x]
        return p

    def union(self, a, b):
        if a not in self.parent:
            self.parent[a] = a
            self.rank[a] = 0
        if b not in self.parent:
            self.parent[b] = b
            self.rank[b] = 0
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            self.parent[ra] = rb
        elif self.rank[ra] > self.rank[rb]:
            self.parent[rb] = ra
        else:
            self.parent[rb] = ra
            self.rank[ra] += 1

def build_groups_df(pairs_df: pd.DataFrame):
    """
    Returns:
      node_groups:   [uuid, group_root, group_id]
      pairs_grouped: original pairs + group_id (by 'uuid' side)
      groups_summary: [group_id, n_nodes, n_edges]
    """
    if pairs_df.empty:
        return (
            pd.DataFrame(columns=["uuid","group_root","group_id"]),
            pairs_df.copy(),
            pd.DataFrame(columns=["group_id","n_nodes","n_edges"]),
        )

    uf = UnionFind()
    for a, b in pairs_df[["uuid","relation_uuid"]].itertuples(index=False):
        uf.union(a, b)

    nodes = pd.unique(pd.concat([pairs_df["uuid"], pairs_df["relation_uuid"]], ignore_index=True))
    roots = [uf.find(x) for x in nodes]
    node_groups = pd.DataFrame({"uuid": nodes, "group_root": roots})
    node_groups["group_id"] = pd.factorize(node_groups["group_root"])[0]

    pairs_grouped = pairs_df.merge(node_groups[["uuid","group_id"]], on="uuid", how="left")

    nodes_per_group = node_groups.groupby("group_id", as_index=False)["uuid"].nunique().rename(columns={"uuid":"n_nodes"})
    edges_per_group = pairs_grouped.groupby("group_id", as_index=False).size().rename(columns={"size":"n_edges"})
    groups_summary = nodes_per_group.merge(edges_per_group, on="group_id", how="left").fillna({"n_edges":0}).astype({"n_edges":int})

    return node_groups, pairs_grouped, groups_summary

def build_uuid_to_orig_map(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a clean mapping [uuid, orig_id] using both ends of the edge list.
    Ensures orig_id is nullable Int64, avoiding '... .0' in CSV.
    """
    left = df[["uuid","orig_id"]].rename(columns={"uuid":"uuid", "orig_id":"orig_id"})
    right = df[["relation_uuid","relation_orig_id"]].rename(columns={"relation_uuid":"uuid", "relation_orig_id":"orig_id"})
    mapping = pd.concat([left, right], ignore_index=True).dropna(subset=["uuid"]).drop_duplicates(subset=["uuid"])
    mapping["orig_id"] = pd.to_numeric(mapping["orig_id"], errors="coerce").astype("Int64")
    return mapping

def export_all_groups(node_groups: pd.DataFrame, uuid_to_orig: pd.DataFrame, path: str) -> pd.DataFrame:
    """Export all groups: [uuid, orig_id, group_id] to CSV."""
    if node_groups.empty:
        out = pd.DataFrame(columns=["uuid","orig_id","group_id"])
        out.to_csv(path, index=False)
        return out
    out = node_groups.merge(uuid_to_orig, on="uuid", how="left")
    out["orig_id"] = out["orig_id"].astype("Int64")
    out.to_csv(path, index=False)
    return out

def main() -> None:
    """Run full pipeline for this step and write all_groups_with_orig.csv."""
    df = run_query()
    print("pair count:", len(df))

    node_groups, pairs_with_group, groups_summary = build_groups_df(df)
    print("\nGroup summary (top 10):\n", groups_summary.sort_values("n_nodes", ascending=False).head(10))

    uuid_to_orig = build_uuid_to_orig_map(df)
    out = export_all_groups(node_groups, uuid_to_orig, path="all_groups_with_orig.csv")

    if not groups_summary.empty:
        print(f"\nExported {len(groups_summary)} groups with {len(out)} uuids to all_groups_with_orig.csv")
    else:
        print("\nNo groups found; exported empty CSV.")

if __name__ == "__main__":
    main()