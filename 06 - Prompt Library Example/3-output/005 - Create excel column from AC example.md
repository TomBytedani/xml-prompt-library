Instructions for human: First, copy the Acceptance Criteria table into an empty Excel, clean it up and line up the Criteria with the filled cells/rows. And then paste it as CSV file in this prompt.

Prompt:
`````````xml
<csv_file>
paste here
</csv_file>
<task>
Given the csv_file that contains a table of acceptance criteria, for each row produce a Test Condition Checklist Description that incorporates the content of the cells with the title of the column (Criteria, Given, When, Then). It shouldn't leave out any details. Output each description in a TSV formatted code block so that if I copypaste it the text is pasted in a single column. Beware of some CSV fields that may be on multiple lines and therefore encased in quotes.
</task>
<example_output>
Criteria: appNAME admin data stored on AF as technical manager; Given: The contract is in ready for onboarding status; When: the dealer enters data into the dedicated “appNAME admin data” section:; Then: the contact is stored on AF as Technical manager
Criteria: appNAME admin data stored on AF as technical manager; Given: The contract is in to be reviewed (data quality)status; When: appNAME admin data hasn’t been entered by dealer; Then: SIS must enter data of the contact that will be stored on AF as Technical manager
Criteria: appNAME admin data mandatory for the SIS; Given: The contract is in to be reviewed (data quality) status; When: the SIS user either deletes mandatory data entered by dealer from the dedicated “appNAME admin data” section or doesn’t enter data in case of empty fields; Then: the “Confirm review and involve Credit Risk” button is disabled
Criteria: Technical manager data update; Given: A technical manager is already available in the contacts list on AF; When: the SIS edits it on AF; Then: Existing technical manager data on AF is overwritten by new data
Criteria: Contract activation: Email to the company address; Given: The customer provides the company email for general communication; When: the contract is in activated status; Then: the contract activation email containing the “welcome letter” pdf is sent to the company address.
Criteria: Contract activation: Email to the company address; Given: the email is confirmed; When: the contract is active; Then: the appNAME admin activation email is sent to the technical manager address
Criteria: New contract for the same customer; Given: The TM already exists for the company; When: the dealer is in the ready for onboarding page; Then: the appNAME admin section is hidden
Criteria: New contract for the same customer; Given: The TM already exists for the company; When: the SIS is in the to be reviewed (Data Quality) page; Then: the appNAME admin section is hidden
</example_output>
`````````
