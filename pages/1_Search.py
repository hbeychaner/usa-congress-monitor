import streamlit as st
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy import create_engine, Column, Integer, String, DateTime, and_

Base = declarative_base()

class BillModel(Base):
    __tablename__ = 'bills'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    congress = Column(Integer, nullable=False)
    latest_action_date = Column(DateTime, nullable=False)
    latest_action_text = Column(String, nullable=False)
    number = Column(Integer, nullable=False)
    origin_chamber = Column(String, nullable=False)
    origin_chamber_code = Column(String, nullable=False)
    title = Column(String, nullable=False)
    type = Column(String, nullable=False)
    update_date = Column(DateTime, nullable=False)
    update_date_including_text = Column(DateTime, nullable=False)
    url = Column(String, nullable=False)

# Set up the database connection
engine = create_engine('sqlite:///congress_bills.db')
Session = sessionmaker(bind=engine)
session = Session()

# Streamlit form for input
st.title("Congress Bills Filter")

with st.form("filter_form"): # Every input should have a on/off tick box
    congress_number = st.number_input("Congress Number", min_value=0, step=1, format="%d")
    congress_number_box = st.checkbox("Filter Congress")
    chamber = st.selectbox("Chamber", options=["", "House", "Senate"])
    chamber_box = st.checkbox("Filter Chamber")
    from_date = st.date_input("From Date")
    to_date = st.date_input("To Date")
    latest_action_date = st.date_input("Latest Action Date")
    latest_action_date_box = st.checkbox("Filter Latest Action Date")
    number = st.number_input("Bill Number", min_value=0, step=1, format="%d")
    number_box = st.checkbox("Filter Bill Number")
    
    # Submit button
    submitted = st.form_submit_button("Search")

# Check if the form is submitted
if submitted:
    # Step 3: Build a Dynamic Query
    query = session.query(BillModel)

    if congress_number_box:
        query = query.filter(BillModel.congress == congress_number)
    if chamber:
        query = query.filter(BillModel.origin_chamber == chamber)
    if from_date and to_date:
        query = query.filter(
            and_(
                BillModel.latest_action_date >= from_date,
                BillModel.latest_action_date <= to_date
            )
        )
    if latest_action_date_box:
        query = query.filter(BillModel.latest_action_date == latest_action_date)
    if number_box:
        query = query.filter(BillModel.number == number)
    # Execute the query
    results = query.all()
    st.write(f"Found {len(results)} bills")
    for bill in results:
        st.write(f"Title: {bill.title}, Congress: {bill.congress}, Chamber: {bill.origin_chamber}, Date: {bill.latest_action_date}")

# Add button for printing all records in the whole database
if st.button("Print All Records"):
    all_bills = session.query(BillModel).all()
    for bill in all_bills:
        st.write(f"Title: {bill.title}, Congress: {bill.congress}, Chamber: {bill.origin_chamber}, Date: {bill.latest_action_date}")
