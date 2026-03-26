<output_column_mapping>
1. `ID` - start with 1 and increase for each row
2. `Summary` - should contain the text after the corresponding "Criteria:" and until the first semicolon
3. `Description` - should contain the text after the corresponding "Given:" and until the second semicolon
4. `Label` - should always include the content "SIT,GatePortal"
5. `Action` - should contain the text after the corresponding "When:" and until the third semicolon
6. `Data` - should remain empty but the column should be still present
7. `Expected Result` - should contain the text after the corresponding "Then:" and until the end of the single given entry
8. `Test Type` - should always contain "Manual" for each entry

This mapping should be repeated for each excel_input_cells and outputted in TSV format for easy copypasting. Don't leave anything out.
</output_column_mapping>