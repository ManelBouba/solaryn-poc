from pathlib import Path
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]

def test_saved_climate_run_and_result_survives_navigation():
    app=AppTest.from_file(str(ROOT/'app/streamlit_app.py'),default_timeout=90).run()
    next(b for b in app.button if b.label=='Module Recommendation').click().run()
    assert not app.exception
    next(b for b in app.button if b.label=='Run evidence-based comparison').click().run()
    assert not app.exception
    run_id=app.session_state['pilot_last_run']
    assert any('2,073.4' in x.value for x in app.info)
    app.run()
    assert app.session_state['pilot_last_run']==run_id
    assert not app.exception
    next(b for b in app.button if b.label=='Downloads').click().run()
    assert not app.exception
    assert any(s.label=='Analysis revision' for s in app.selectbox)
