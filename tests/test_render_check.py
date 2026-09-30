from pathlib import Path

import pytest

from cvforge.config import BUILTIN_TEMPLATES
from cvforge.core.check import check_docx, check_pdf
from cvforge.core.render import get_template, list_templates, new_template, render_docx, render_pdf
from cvforge.models import CVBullet, TailoredCV

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def cv() -> TailoredCV:
    return TailoredCV.model_validate_json((FIX / "sample_cv.json").read_text(encoding="utf-8"))


ALL = sorted(list_templates([BUILTIN_TEMPLATES]))


def test_all_expected_templates_exist():
    assert {
        "ats-classic",
        "ats-modern",
        "compact",
        "corporate",
        "executive",
        "tech",
        "timeline",
        "elegant",
        "sidebar",
    } <= set(ALL)


@pytest.mark.parametrize("name", ALL)
@pytest.mark.parametrize("lang", ["pl", "en"])
def test_templates_render_and_pass_checks(tmp_path, cv, name, lang):
    cv.language = lang
    tpl = get_template(name, [BUILTIN_TEMPLATES])
    layout = render_pdf(cv, tpl, tmp_path / "cv.pdf")
    render_docx(cv, tpl, tmp_path / "cv.docx")
    pdf = check_pdf(tmp_path / "cv.pdf", cv, tpl, layout, previews_dir=tmp_path / "prev")
    docx = check_docx(tmp_path / "cv.docx", cv)
    problems = [i for i in pdf.items if i.status != "pass"]
    if tpl.ats_safe:
        assert not problems, problems
    else:  # design templates only warn about themselves
        assert [i.rule for i in problems] == ["template_ats_safe"], problems
    assert docx.status == "pass", docx.items
    assert pdf.previews and (tmp_path / "prev" / pdf.previews[0]).exists()
    present = "obecnie" if lang == "pl" else "Present"
    assert present in (tmp_path / "cv.html").read_text(encoding="utf-8")


def test_check_detects_overflowing_page_count(tmp_path, cv):
    tpl = get_template("compact", [BUILTIN_TEMPLATES])  # 1-page target
    long = [CVBullet(text="Zbudowałem i utrzymywałem rozbudowane środowisko " * 3, source_ids=["x"])] * 40
    cv.experience[0].bullets = long
    layout = render_pdf(cv, tpl, tmp_path / "cv.pdf")
    rep = check_pdf(tmp_path / "cv.pdf", cv, tpl, layout)
    item = next(i for i in rep.items if i.rule == "page_count")
    assert item.status == "fail" and rep.pages >= 3


def test_check_detects_missing_email(tmp_path, cv):
    tpl = get_template("ats-classic", [BUILTIN_TEMPLATES])
    render_pdf(cv, tpl, tmp_path / "cv.pdf")
    other = cv.model_copy(deep=True)
    other.contact.email = "someone.else@example.com"
    rep = check_pdf(tmp_path / "cv.pdf", other, tpl)
    assert next(i for i in rep.items if i.rule == "contact_email").status == "fail"


def test_new_template_scaffold(tmp_path):
    base = get_template("ats-modern", [BUILTIN_TEMPLATES])
    dest = new_template("my-style", base, tmp_path)
    assert (dest / "cv.html.j2").exists() and (dest / "style.css").exists()
    assert "my-style" in list_templates([tmp_path, BUILTIN_TEMPLATES])


def test_letter_spacing_is_detected(tmp_path, cv):
    base = get_template("ats-classic", [BUILTIN_TEMPLATES])
    dest = new_template("spaced", base, tmp_path)
    (dest / "style.css").write_text((dest / "style.css").read_text() + "\nh2 { letter-spacing: 0.3em; }\n")
    tpl = get_template("spaced", [tmp_path])
    render_pdf(cv, tpl, tmp_path / "cv.pdf")
    rep = check_pdf(tmp_path / "cv.pdf", cv, tpl)
    assert any(i.rule == "letter_spacing" and i.status == "fail" for i in rep.items)


def test_template_local_font(tmp_path, cv):
    import shutil

    from cvforge.core.render import FONTS_DIR

    dest = new_template("myfont", get_template("ats-classic", [BUILTIN_TEMPLATES]), tmp_path)
    (dest / "fonts").mkdir()
    shutil.copy(FONTS_DIR / "Caladea-Regular.ttf", dest / "fonts" / "Mine.ttf")
    toml = dest / "template.toml"
    text = toml.read_text().replace('fonts = ["NotoSans"]', "fonts = []")
    text = text.replace("[docx]", '[[font]]\nfamily = "Mine"\nfile = "fonts/Mine.ttf"\n\n[docx]')
    toml.write_text(text)
    (dest / "style.css").write_text((dest / "style.css").read_text().replace('"Noto Sans"', '"Mine"'))
    tpl = get_template("myfont", [tmp_path])
    render_pdf(cv, tpl, tmp_path / "cv.pdf")
    fonts = next(i for i in check_pdf(tmp_path / "cv.pdf", cv, tpl).items if i.rule == "fonts_embedded").detail
    assert "Mine" in fonts and "Noto" not in fonts


def test_template_preview_is_cached(tmp_path):
    from cvforge.core.render import template_preview

    tpl = get_template("tech", [BUILTIN_TEMPLATES])
    png = template_preview(tpl, tmp_path)
    assert png.exists() and template_preview(tpl, tmp_path) == png


def test_fit_to_pages_trims_one_item_at_a_time(tmp_path, cv):
    from cvforge.core.render import fit_to_pages

    tpl = get_template("ats-classic", [BUILTIN_TEMPLATES]).model_copy(update={"max_pages": 1})
    extra = [
        CVBullet(text=f"Dodatkowe osiągnięcie numer {i} opisane w kilku słowach dla testu.", source_ids=["x"])
        for i in range(25)
    ]
    cv.experience[0].bullets += extra
    fitted, layout, removed = fit_to_pages(cv, tpl, tmp_path / "cv.pdf")
    assert layout.pages == 1 and removed
    assert len(fitted.experience[0].bullets) < len(cv.experience[0].bullets)
    # the most relevant (first) bullets survive; nothing is rewritten
    assert fitted.experience[0].bullets[0].text == cv.experience[0].bullets[0].text
    assert fitted.summary == cv.summary or cv.summary.startswith(fitted.summary)


def test_fit_to_pages_leaves_short_cv_alone(tmp_path, cv):
    from cvforge.core.render import fit_to_pages

    tpl = get_template("ats-classic", [BUILTIN_TEMPLATES]).model_copy(update={"max_pages": 1})
    fitted, layout, removed = fit_to_pages(cv, tpl, tmp_path / "cv.pdf")
    assert layout.pages == 1 and removed == [] and fitted == cv
