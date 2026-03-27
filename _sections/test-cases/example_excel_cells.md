```````````xml
<example_excel_cells>
|Criteria: Imported configuration flow - new vehicle configuration; Given: A Quotation is created and is not Expired, Declined, or Cancelled; When: A user clicks the "Add Configuration" CTA at the bottom of the Quotation Summary page; Then: The user is redirected to the page for importing a new configuration (simulation or import)|
|Criteria: Imported configuration flow - new vehicle configuration; Given: A new configuration is imported and the user is on the vehicle configuration page; When: The user clicks "Close"; Then: The user is redirected back to the Quotation Summary page without saving changes|
|Criteria: Imported configuration flow - new vehicle configuration; Given: A new configuration is imported and the user is on the vehicle configuration page; When: The user clicks "Confirm"; Then: The Configuration is saved and user is redirected to the Quotation Summary page with the new Configuration|
|Criteria: Imported configuration - number of vehicles; Given: A vehicle configuration is imported into FleetPortal; When: The Vehicle amount parameter is passed from CPQ; Then: The Vehicle amount is disregarded and does not affect the contracts generated from the attached Options|
|Criteria: Add Option flow; Given: A Quotation is not Expired or Cancelled, and the Configuration is not Rejected; When: A user clicks "Add Option"; Then: The user is redirected to a dedicated Option setup page without the stepper, and with a "Close" button at the bottom|
|Criteria: Add Option flow; Given: A user is on the dedicated Option setup page; When: The user clicks "Close"; Then: The system exits the page without saving changes|
|Criteria: Add Option flow; Given: A user is on the dedicated Option setup page; When: The user completes Option setup and clicks "Save"; Then: The Option is saved and linked to the current Quotation|
|Criteria: ISU reviewing a vehicle configuration; Given: An ISU user is viewing a non-eligible Configuration; When: The user clicks the "Edit Configuration" button; Then: The vehicle customisation page is displayed|
|Criteria: ISU reviewing a vehicle configuration; Given: The Configuration has a vehicle body; When: The ISU user accesses the customisation page; Then: The user can edit the vehicle body price|
|Criteria: ISU reviewing a vehicle configuration; Given: An ISU user accesses the customisation page; When: The user sees the Refurbishing Price field; Then: The field is editable and not visible to Dealer users|
|Criteria: ISU reviewing a vehicle configuration; Given: An ISU user changes body price or Refurbishing Price; When: The user clicks "Confirm & Proceed"; Then: All Options in that Configuration are recalculated and the Quotation Summary page is shown|
|Criteria: ISU reviewing a vehicle configuration; Given: An ISU user is reviewing a Configuration; When: The user clicks "Back"; Then: No changes are saved and the user is redirected to the Quotation Summary page|
</example_excel_cells>
```````````
