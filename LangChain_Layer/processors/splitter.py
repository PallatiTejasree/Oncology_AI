from langchain_text_splitters import RecursiveCharacterTextSplitter


def split_text(text: str):

    if not text:
        return []


    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )


    chunks = splitter.split_text(text)

    return chunks