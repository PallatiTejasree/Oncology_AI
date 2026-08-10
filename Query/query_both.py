"""Run an image query together with its report/OCR text."""

import argparse
import json

from Query.pipeline import QueryPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("text", help="Report or OCR text associated with the image")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    result = QueryPipeline(args.device).query_image(args.image, args.text, args.top_k)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
