"""Run an image-similarity query against the image collection."""

import argparse
import json

from Query.retriever import ImageRetriever


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()
    result = ImageRetriever(device=args.device).search_image(args.image, args.top_k)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
