from app.services.preprocessing import detect_sections, preprocess_text


def test_preprocessing_preserves_technical_terms():
    result = preprocess_text("Python\r\n\r\n• C++   and   .NET")
    assert "Python" in result and "C++" in result and ".NET" in result
    assert "\r" not in result


def test_section_detection():
    sections = detect_sections("Skills\nPython, SQL\nEducation\nB.Tech Computer Science")
    assert "Python" in sections["skills"]
    assert "B.Tech" in sections["education"]
