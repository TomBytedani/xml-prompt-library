`````````xml
<instructions>
The user may provide a follow-up prompt containing the parameters for the vehicle used to trigger the defect. In case the user does, you should output the given parameters in an ordered fashion following the vehicleTemplate provided. The outputted vehicle info should be contained in Markdown format and inside a code block for easy copy pasting.
</instructions>
<vehicleTemplate_info>
Below you can find the vehicle template, only edit and/or fill the text strings inside the double codeticks. If one of the specific **bolded** parameters isn't provided, fill it with the string `N/A`.
Since the prompt will be transcribed, look out for transcription errors. Examples of transcription errors and how to correct them could be "nobody"→"No Body" (for Body type param); "Fourty-two see"→"42C" (for the Model versions, which are always two digits + the letter S or C).
<vehicleTemplate_defaults>
By default the parameters OPP code, Model year, Fast charger, Additional Items and Tyres should be left as provided in the template, unless specified by the user in the transcribed prompt.
</vehicleTemplate_defaults>
</vehicleTemplate_info>
<vehicleTemplate>
```markdown
___
### Vehicle Parameters
#### Configuration info
**OPP code**: `N/A`
**Model year**: `MY24`
**Vehicle type**: ``
**Model version**: ``
**List vehicle price**: ``
**Body type**: ``
**Body price**: ``
**Mission type**: ``
**ePTO hours**: `0`
**N° of batteries**: ``
**Fast Charger selected**: `Yes`
**Additional Items Amount**: `N/A`
#### Option info
**Years duration**: ``
**KMs annual**: ``
**Easy/Energy/eManager**: ``
**Tyres**: `Yes`
```
</vehicleTemplate>
<follow-up-prompt>

</follow-up-prompt>
`````````
