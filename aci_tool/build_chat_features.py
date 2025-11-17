import pandas as pd
from .chat_semantic import extract_chat_features_from_jsonl

in_path = "data/raw/negotiations.jsonl" # TODO make a relative path
out_path = "data/processed/chat_features.csv" # TODO make a relative path

rows = list(extract_chat_features_from_jsonl(in_path))
df = pd.DataFrame(rows)
df.to_csv(out_path, index=False)
print(f"Wrote {len(df)} chats to {out_path}")
