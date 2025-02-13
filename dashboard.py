import streamlit as st
from PIL import Image
from src.streamlit_components import init_footer

# Set page config
st.set_page_config(
	layout="wide",
	#initial_sidebar_state="collapsed",  # Can be "auto", "expanded", "collapsed"
	page_title="Congress Tracker Dashboard",
    page_icon=Image.open('src/streamlit/acorn.png'),
    menu_items={
		'Get Help': "mailto:hbeychaner@gmail.com",
		'About': "#"}
)

st.title("Congress Tracker Dashboard")
 
footer=init_footer()
st.markdown(footer,unsafe_allow_html=True)
