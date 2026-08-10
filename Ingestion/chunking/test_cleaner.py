from cleaner import clean_text

sample = """

Patient has lung cancer.


CT     scan shows multiple nodules.



MRI confirms metastasis.

"""

print(clean_text(sample))