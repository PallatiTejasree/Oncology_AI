"""Run a text query against text and image collections."""

import argparse
import json

from Query.pipeline import QueryPipeline
from Query.retriever import ImageRetriever, TextRetriever


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--device", default="auto")
    parser.add_argument(
        "--include-legacy",
        action="store_true",
        help="Include unlabelled legacy images in text-to-image results",
    )
    args = parser.parse_args()
    if args.include_legacy:
        text = TextRetriever(device=args.device).search(args.query, args.top_k)
        images = ImageRetriever(device=args.device).search_text(
            args.query, args.top_k, include_legacy=True
        )
        result = {"query_type": "text", "text_results": text, "image_results": images}
    else:
        result = QueryPipeline(args.device).query_text(args.query, args.top_k)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
