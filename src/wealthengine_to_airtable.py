"""
Wealthengine → Airtable CSV Converter
Uploads a WealthEngine export into the airtable development base.

Usage (via launcher):
    Open main.py, select this script, and choose your input file.

Usage (command line):
    python wealthengine_to_airtable.py

The input file is configured in the CONFIG section below.
One output file is written.
    potential_duplicates.txt

See the examples/ folder for properly formatted input/output examples.
"""
# This is the csv format for the export. However, ideally all necessary cols have index calculated in case it changes.
#WE Run ID,WE Record ID,originalID,originalID2,Search Date,Prefix,First Name,Middle Name,Last Name,Suffix,"Address 1,2 and 3",City,State,Zip,2nd Person Last Name,2nd Person First Name,2nd Person Middle Name,Business name,Client supplied business phone,Business name 2,Client supplied business phone 2,Business name 3,Client supplied business phone 3,Total Giving,Number of Gifts,First Gift Date,First Gift Amount,Last Gift Date,Last Gift Amount,Largest Gift Date,Largest Gift Amount,Client supplied Age,Client supplied Birthday,Client Supplied Graduation Date,Gender,Age,Date of Birth,P2G Score Combo,P2G Description,P2G Score (first digit),P2G Score (second digit),Total Assets,Net Worth,Cash on Hand,Estimated Annual Donations,Gift Capacity Range,Gift Capacity Rating,Gift Capacity - Income,Gift Capacity - Real Estate,Gift Capacity - Stock,Gift Capacity - Pension,Gift Capacity - Donations,Estimated Gift Capacity,Influence Rating,Inclination: Affiliation,Inclination: Giving,Bequest,Annuity,Trust,Income,Pension,Real Estate Value,Real Estate Properties,Stock Direct Holdings,Stock Total Value,Charitable Donations,Political Donations,Total Donations,Business Ownership,Co. Sales Volume,Aircraft Owner,Boat Owner,Children,Inner Circle Connected,Inner Circle Member,Major Donor Member,Match Count,Folder Name,QOM - Aircraft,QOM - Airmen,QOM - D&B,QOM - D&B State Biz Reg,QOM - Do Not Mail,QOM - Charitable Donations,QOM - Fed Election Campaign,QOM - GuideStar Foundation,QOM - GuideStar Directors,QOM - Household Profile,QOM - Hoovers,QOM - Major Donor,QOM - Market Guide,QOM - IRS Section 527 Directors,QOM - IRS Section 527 Political Org,QOM - Pension,QOM - Philanthropic Donations,QOM - Real Estate,QOM - State Political,QOM - SSA Death Index,QOM - Wealth ID Securities,QOM -- Merchant Vessels,QOM -- Marquis Whos Who,Attribute 1,Attribute 2,Attribute 3,Attribute 4,Attribute 5,Attribute 6,Attribute 7,Attribute 8,Attribute 9,Attribute 10,Attribute 11,Attribute 12,Attribute 13,Attribute 14,Attribute 15,Deceased Indicator,Personal email 1,Personal email 2,Personal email 3,Business phone 1,Business phone 2,Business phone 3,Business email 1,Business email 2,Business email 3,Personal Phone 1,Personal Phone 2,Personal Phone 3,Email Verification Status - personal email 1,Email Verification Status - personal email 2,Email Verification Status - personal email 3,Email Verification Status - Business email 1,Email Verification Status - Business email 2,Email Verification Status - Business email 3,Email Verification Date,WealthScore
# Airtable api key is in .env as AIRTABLE_KEY
# api_id is dictionary for every id value needed.
api_id = {"Name" : "fldJDAn24IkdBz602"
          "Principal First" : "fldxtrz1GfFLPSECr"
          "Principal Last" : "fld3imK3izgq6GSJT"
          "Email" : "fldou36sB8VLuUgVh"
          "Additional Emails" : "flduqGJb81A9QTbNa"
          "Location (city, state)" : "flduYaaFGuXgLq9Cz"
          "Wealth Score" : "fldwunFpf8SaxP165"
          "P2G Score 1" : "fld7tPfJZBguRW5Dx"
          "P2G Score 2" : "fld29iDtSMHNx3MG2"
          "Estimated Annual Donations" : "fldrBXNxYicGWooPT"
          "Gift Capacity Range" : "fld1aR6CN5f3RUgKn"
          "Charitable Donations" : "fld2mhgTzxlaWfT2V"
          "Political Donations" : "fld0Gyn9rBGJl7EWT"
          "Total Donations" : "fldTAH9tb5tlorobz"
          }


def main(input: str) -> None:
    """
    Reads all lines of the csv file, and performs the correct operations
    
    Args:
        input: The input file name
    """
    read lines, 
    for each line process(line)
    write potential_duplicates.txt to include all names in potential_dupes # could just make this a function for simplicity

potential_dupes: list[str] = []

def process(line: str) -> None:
    """
    Weeds out potential bad data with no name or match
    Looks for the user in airtable. 
    If found, updates that user.
    If not found, makes a new record and writes a txt file to check for dupes 
    manually.

    Args:
        line: one line of the csv file with info on a person
    
    Outputs:
        None
    """
    first_name: str = whatever slot the first name col is in the csv
    last_name:str = hatever slot the first name col is in the csv
    if first_name == "" or last_name == "":
        return None
    p2g_description: str = whatever slot p2g desc is in
    if p2g_description == "No Match":
        return None

    record = find_user(first_name, last_name)

    if record is None:
        write_new(line)
        potential_dupes.append(first_name + last_name)
    else:
        update(line)

def find_user(first_name: str, last_name: str) -> int | None:
    """
    Attempts to find a record in Airtable matching first/last

    Args:
        first_name: The user's first name
        last_name: The user's last name
    
    Returns:
        Returns None if no good match
        Returns the record's row number or other id number to be used by the api to modify the row
    """
    # Returns a positive result if first and last name(lowered/cleaned and everything) are in the principal first/last col of a record.
    # Both the first and last, not one or the other.
    # If there are multiple records with the same criteria, return none.
    #  

def write_new(line):
    """
    Write a new record to airtable
    """
    However writing a new record works, for every value in api_id, it should take the value from the line.
    Name = First Name + Last Name
    Principal First/Last = First Name/Last Name
    Email =
    Location = city, state
    Should be obvious what maps to what, just ask if unclear

def update(line):
    """
    Updates an existing record
    """
    Similar to write_new.
    Name = First + Last
    Principal First/Last = First Name/Last Name
    Only update email if none existing
    Location = city, state
    everything else should be simple, just a 1:1 copy
    