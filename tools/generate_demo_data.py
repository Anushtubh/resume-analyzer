from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
RESUME_DIR = ROOT / "sample_data" / "resumes"
JOB_DIR = ROOT / "sample_data" / "job_descriptions"
RESUME_DIR.mkdir(parents=True, exist_ok=True)
JOB_DIR.mkdir(parents=True, exist_ok=True)

RESUMES = {
    "01_maya_ml_engineer": """Maya Sharma\nMachine Learning Engineer\n\nSUMMARY\nMachine Learning Engineer with 4 years of experience building production recommendation and forecasting systems.\n\nSKILLS\nPython, Machine Learning, Deep Learning, PyTorch, TensorFlow, SQL, Pandas, NumPy, Docker, Git, AWS\n\nEXPERIENCE\nMachine Learning Engineer at Vision Labs - 4 years\n\nPROJECTS\nRecommendation System using PyTorch and FAISS\n\nEDUCATION\nB.Tech Computer Science""",
    "02_arjun_data_scientist": """Arjun Rao\nData Scientist\n\nSUMMARY\nData Scientist with 3 years of experience in predictive analytics and experimentation.\n\nSKILLS\nPython, Machine Learning, Scikit-learn, Pandas, NumPy, SQL, Tableau, Git\n\nEXPERIENCE\nData Scientist at Insight Analytics - 3 years\n\nPROJECTS\nCustomer churn prediction and A/B testing dashboard\n\nEDUCATION\nMaster of Data Science""",
    "03_sara_web_developer": """Sara Khan\nFrontend Web Developer\n\nSKILLS\nJavaScript, TypeScript, React, HTML, CSS, Node.js, GitHub\n\nEXPERIENCE\nWeb Developer at Pixel Works - 3 years\n\nPROJECTS\nResponsive e-commerce website with React and Node.js\n\nEDUCATION\nB.Tech Information Technology""",
    "04_vikram_python_developer": """Vikram Patel\nPython Backend Developer\n\nSKILLS\nPython, Django, Flask, FastAPI, PostgreSQL, MongoDB, Docker, Git, SQL\n\nEXPERIENCE\nPython Developer at API Systems - 5 years\n\nPROJECTS\nFastAPI order management service\n\nEDUCATION\nB.Tech Computer Science""",
    "05_neha_data_analyst": """Neha Iyer\nData Analyst\n\nSKILLS\nSQL, MySQL, Python, Pandas, Power BI, Tableau, Excel\n\nEXPERIENCE\nData Analyst at Retail Metrics - 2 years\n\nPROJECTS\nPower BI sales reporting and customer segmentation\n\nEDUCATION\nBachelor of Business Analytics""",
    "06_rohan_cloud_engineer": """Rohan Mehta\nCloud Engineer\n\nSKILLS\nAWS, Azure, Docker, Kubernetes, Python, Git, SQL\n\nEXPERIENCE\nCloud Engineer at CloudScale - 4 years\n\nPROJECTS\nKubernetes deployment automation on AWS\n\nEDUCATION\nB.Tech Computer Engineering""",
    "07_isha_ai_engineer": """Isha Verma\nAI Engineer\n\nSKILLS\nPython, Deep Learning, TensorFlow, Keras, Computer Vision, PyTorch, Docker, Git\n\nEXPERIENCE\nAI Engineer at Robotics AI - 3 years\n\nPROJECTS\nComputer vision quality inspection using TensorFlow\n\nEDUCATION\nMaster of Artificial Intelligence""",
    "08_karan_backend_developer": """Karan Singh\nBackend Developer\n\nSKILLS\nJava, C#, SQL, PostgreSQL, Django, Docker, GitHub\n\nEXPERIENCE\nBackend Developer at Enterprise Apps - 4 years\n\nPROJECTS\nMicroservices billing platform\n\nEDUCATION\nB.Tech Software Engineering""",
    "09_ananya_software_engineer": """Ananya Das\nSoftware Engineer\n\nSKILLS\nJava, C++, C, JavaScript, SQL, Git, Docker\n\nEXPERIENCE\nSoftware Engineer at Core Products - 3 years\n\nPROJECTS\nDistributed transaction processing service\n\nEDUCATION\nB.Tech Computer Science""",
    "10_dev_nlp_engineer": """Dev Menon\nNLP Engineer\n\nSUMMARY\nNLP Engineer with 2 years of experience building text classification and search systems.\n\nSKILLS\nPython, NLP, Machine Learning, Hugging Face, PyTorch, FAISS, SQL, Docker, Git\n\nEXPERIENCE\nNLP Engineer at Language Labs - 2 years\n\nPROJECTS\nResume semantic search with PyTorch and FAISS\n\nCERTIFICATIONS\nNatural Language Processing Specialization\n\nEDUCATION\nB.Tech Computer Science""",
}

JDS = {
    "machine_learning_engineer.txt": """Machine Learning Engineer\nWe are looking for a Machine Learning Engineer with 2+ years of experience in Python, machine learning and deep learning. Experience with PyTorch or TensorFlow is preferred. Bachelor's degree in Computer Science is required. AWS and SQL are useful.""",
    "data_scientist.txt": """Data Scientist\nWe need a Data Scientist with 2+ years of experience in Python, machine learning, SQL, Pandas and NumPy. Experience with Tableau or Power BI and a bachelor's degree is preferred.""",
    "backend_engineer.txt": """Backend Engineer\nSeeking a backend engineer with 3+ years of experience in Python, FastAPI or Django, SQL, PostgreSQL, Docker and Git. A computer science degree is preferred.""",
}


def write_pdf(path: Path, text: str):
    # Minimal one-page, text-based PDF fixture. Runtime extraction still uses PyMuPDF.
    lines = text.splitlines()[:55]
    commands = ["BT", "/F1 10 Tf", "54 760 Td", "14 TL"]
    for line in lines:
        safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands.append(f"({safe}) Tj T*" if safe else "T*")
    commands.append("ET")
    stream = "\n".join(commands).encode("latin-1", errors="replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    output.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    output.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    path.write_bytes(output)


def write_docx(path: Path, text: str):
    paragraphs = "".join(f"<w:p><w:r><w:t>{escape(line)}</w:t></w:r></w:p>" for line in text.splitlines())
    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{paragraphs}<w:sectPr/></w:body></w:document>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'''
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", rels)
        archive.writestr("word/document.xml", document_xml)


for index, (name, text) in enumerate(RESUMES.items()):
    for old in RESUME_DIR.glob(f"{name}.*"):
        old.unlink()
    if index % 2 == 0:
        write_pdf(RESUME_DIR / f"{name}.pdf", text)
    else:
        write_docx(RESUME_DIR / f"{name}.docx", text)
for filename, text in JDS.items():
    (JOB_DIR / filename).write_text(text, encoding="utf-8")
print(f"Generated {len(RESUMES)} demo resumes and {len(JDS)} demo job descriptions.")
