"""Streamlit UI helper components used by the app.

This module provides small presentation helpers used by the Streamlit
front-end. Keep helpers minimal and return HTML/CSS snippets only.
"""

from src.utils.logger import get_logger

logger = get_logger(__name__)


def init_footer() -> str:
    """Return the HTML/CSS snippet used for the app footer.

    Returns:
        str: HTML markup for the footer element.
    """
    return """<style>
a:link , a:visited{
color: blue;
background-color: transparent;
text-decoration: underline;
}

a:hover,  a:active {
color: red;
background-color: transparent;
text-decoration: underline;
}

.footer {
position: fixed;
left: 0;
bottom: 0;
width: 100%;
background-color: white;
color: black;
text-align: center;
}
</style>
<div class="footer">
<p>Developed with ❤ by Brandon Eychaner</a></p>
</div>
"""
