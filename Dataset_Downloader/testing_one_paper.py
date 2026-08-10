from europe_pmc import EuropePMC
import requests

pmc = EuropePMC()

article = pmc.fetch("PMC13297349")

print(article.title)
print(article.pdf_url)

response = requests.get(article.pdf_url)

with open("PMC13297349.pdf", "wb") as f:
    f.write(response.content)

print("Downloaded Successfully")