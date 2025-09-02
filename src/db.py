from typing import Optional

from sqlalchemy import Column, DateTime, Integer, String, create_engine, inspect
from sqlalchemy.orm import declarative_base, sessionmaker

from src.data_structures.bills import Bill

Base = declarative_base()
# Create an SQLite database in memory or on disk
engine = create_engine("sqlite:///congress_bills.db")


class BillModel(Base):
    """
    A SQLAlchemy model for the bills table.
    """

    __tablename__ = "bills"

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


# Create all tables
def create_tables():
    """
    Create the tables in the database.
    """
    # Check if table exists
    inspector = inspect(engine)
    if not inspector.has_table(BillModel.__tablename__):
        Base.metadata.create_all(engine)


# Create a configured "Session" class
Session = sessionmaker(bind=engine)
session = Session()


def insert_bills_into_db(bills: list[Bill], session) -> None:
    """
    Insert bills into the database.

    Args:
        bills (list[Bill]): A list of Bill objects.
        session (Session): The database session.

    Returns:
        None
    """
    for bill in bills:
        bill_model = BillModel(
            congress=bill.congress,
            latest_action_date=bill.latest_action.action_date,
            latest_action_text=bill.latest_action.text,
            number=bill.number,
            origin_chamber=bill.origin_chamber,
            origin_chamber_code=bill.origin_chamber_code,
            title=bill.title,
            type=bill.type,
            update_date=bill.update_date,
            update_date_including_text=bill.update_date_including_text,
            url=bill.url,  # type: ignore
        )
        session.add(bill_model)
    session.commit()


def get_bills_from_db(
    session,
    congress: Optional[int] = None,
    chamber: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    latest_action_date: Optional[str] = None,
    number: Optional[int] = None,
) -> list[BillModel]:
    """
    Retrieve bills from the database based on the provided filters.

    Args:
        session (Session): The database session.
        congress (int): The Congress number.
        chamber (str): The chamber of origin.
        from_date (str): The start date for the search in the format "YYYY-MM-DDTHH:MM:SSZ".
        to_date (str): The end date for the search in the format "YYYY-MM-DDTHH:MM:SSZ".
        latest_action_date (str): The latest action date.
        number (int): The bill number.

    Returns:
        list[BillModel]: A list of BillModel objects.
    """
    query = session.query(BillModel)
    if congress:
        query = query.filter(BillModel.congress == congress)
    if chamber:
        query = query.filter(BillModel.origin_chamber == chamber)
    if from_date:
        query = query.filter(BillModel.update_date >= from_date)
    if to_date:
        query = query.filter(BillModel.update_date <= to_date)
    if latest_action_date:
        query = query.filter(BillModel.latest_action_date == latest_action_date)
    if number:
        query = query.filter(BillModel.number == number)
    return query.all()
