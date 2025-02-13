import streamlit as st

# Title of the dashboard
st.title('Congress Tracker Dashboard')

# Dropdown menu with placeholder values
dropdown_options = [f"Option {i}" for i in range(1, 11)]
selected_option = st.selectbox('Select an option:', dropdown_options)

# Checkboxes with placeholder values
checkbox_options = [f"Stage {i}" for i in range(1, 11)]
selected_stages = []
for option in checkbox_options:
    if st.checkbox(option):
        selected_stages.append(option)

# Display selected values
st.write('Selected Option:', selected_option)
st.write('Selected Stages:', selected_stages)