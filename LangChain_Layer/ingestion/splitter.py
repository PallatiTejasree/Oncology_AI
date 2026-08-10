from langchain_text_splitters import RecursiveCharacterTextSplitter


class MedicalDocumentSplitter:

    def __init__(self,
                 chunk_size=800,
                 chunk_overlap=150):

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n",
                "\n",
                ". ",
                "; ",
                ", ",
                " ",
                ""
            ]
        )

    def split(self, text):

        chunks = self.splitter.split_text(text)

        documents = []

        for i, chunk in enumerate(chunks):

            documents.append({

                "chunk_id": i + 1,

                "text": chunk,

                "characters": len(chunk),

                "words": len(chunk.split())

            })

        return documents