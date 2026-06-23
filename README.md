# FairVote
Scripts and whatnot for FairVote  
  
## Convert Donors
Takes an input csv file like in planner carryover of the **prospecting table**  
on airtable, cleans it using the **donor_checks.csv** to remove people that  
have already donated, and then outputs in a format that can be uploaded to  
Prospects Overview.  
  
## Givebutter to WealthEngine
Takes the Givebutter individuals export as a csv file and converts it into a 
screenable wealthengine csv import. Takes the input file from goodbutter in the
form of **examples/givebutter_to_wealthengine_sample.csv** and cleans it for 
upload. Also screens it for common misattributed companies that are
classified as individuals in goodbutter. It produces a csv ready to be uploaded
to WealthEngine using a template that consists of the following columns:  
First Name, Last Name, Primary Address Line 1, Primary Address Line 2, Primary
 Address City, Primary Address State, Primary Address Zip, Total Giving, Phone,
 Email.  
Not all values need to be filled out, but they do provide better results.
If minimal data on a person, there will likely not be a good match, so if bad 
data, you might want to manually check for duplicates or additional info stored
in goodbutter, airtable, or keela. After screening, you will get a list of people
in WealthEngine to analyze or build models off of.  
  
## WealthEngine To Airtable
Takes an input csv that is exported from wealth engine. Built off of the default
export, but should work with any form, as long as the essential data is exported.
This default can be seen at **examples/wealthengine_to_airtable_sample.csv**.
You must have an [airtable api key](https://airtable.com/create/tokens) for this to work.
It only needs the data.records:read and data.records:write scopes, and only
needs to see the development base. It should be stored in a .env file like 
so. Just one line is needed.
```
AIRTABLE_KEY=key_here
```
The program looks for contacts that match the first and last name, as long as it is included.
This means that John & Lisa Smith will be a match for a WE profile for John Smith.
If there are multiple matches, it creates a new entry at the bottom of the base
for the name, with all WE info and adds the name to **new_records.txt**. This txt
file will have a list of names for manual checkig for duplicates and will also
include any names that could not be matched (in goodbutter but not Airtable).
It should automatically update all successful matches due to the API integration.