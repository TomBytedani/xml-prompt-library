<example_output>
```tsv
Issue ID Summary Description Label Action Data Expected Result Test Type
1 Imported configuration flow - new vehicle configuration - Add button A Quotation is created and is not Expired, Declined, or Cancelled SIT,GatePortal A user clicks the “Add Configuration” CTA at the bottom of the Quotation Summary page  The user is redirected to the page for importing a new configuration (simulation or import) Manual
2 Imported configuration flow - new vehicle configuration -Close  A new configuration is imported and the user is on the vehicle configuration page SIT,GatePortal The user clicks “Close”  The user is redirected back to the Quotation Summary page without saving changes Manual
3 Imported configuration flow - new vehicle configuration - Confirm A new configuration is imported and the user is on the vehicle configuration page SIT,GatePortal The user clicks “Confirm”  The Configuration is saved and user is redirected to the Quotation Summary page with the new Configuration Manual
4 Imported configuration - number of vehicles A vehicle configuration is imported into GATE Portal SIT,GatePortal The Vehicle amount parameter is passed from CPQ  The Vehicle amount is disregarded and does not affect the contracts generated from the attached Options Manual
5 Add Option flow - Add A Quotation is not Expired or Cancelled, and the Configuration is not Rejected SIT,GatePortal A user clicks “Add Option”  The user is redirected to a dedicated Option setup page without the stepper, and with a “Close” button at the bottom Manual
6 Add Option flow - Close A user is on the dedicated Option setup page SIT,GatePortal The user clicks “Close”  The system exits the page without saving changes Manual
7 Add Option flow - Save A user is on the dedicated Option setup page SIT,GatePortal The user completes Option setup and clicks “Save”  The Option is saved and linked to the current Quotation Manual
8 SIS reviewing a vehicle configuration - Non eligible config A SIS user is viewing a non-eligible Configuration SIT,GatePortal The user clicks the “Edit Configuration” button  The vehicle customisation page is displayed Manual
9 SIS reviewing a vehicle configuration - Vehicle body The Configuration has a vehicle body SIT,GatePortal The SIS user accesses the customisation page  The user can edit the vehicle body price Manual
10 SIS reviewing a vehicle configuration - Customisation page A SIS user accesses the customisation page SIT,GatePortal The user sees the Refurbishing Price field  The field is editable and not visible to Dealer users Manual
11 SIS reviewing a vehicle configuration - Body price or refurbishment A SIS user changes body price or Refurbishing Price SIT,GatePortal The user clicks “Confirm & Proceed”  All Options in that Configuration are recalculated and the Quotation Summary page is shown Manual
12 SIS reviewing a vehicle configuration - Config reviewing A SIS user is reviewing a Configuration SIT,GatePortal The user clicks “Back”  No changes are saved and the user is redirected to the Quotation Summary page Manual
13 SIS reviewing a vehicle configuration - Config reviewed A SIS user has reviewed a Configuration SIT,GatePortal The user selects Accept or Reject, enters a comment, and clicks Submit  The review is submitted and stored Manual
```
</example_output>