from django import forms

from apps.ncsbe.constants import COUNTY_ID_MAP


class CountyForm(forms.Form):
    county_name = forms.CharField()

    def clean_county_name(self):
        county_name = self.cleaned_data["county_name"].upper()
        if county_name not in COUNTY_ID_MAP:
            raise forms.ValidationError(f"'{county_name}' is not a valid NC county.")
        return county_name


class VoterHistoryForm(forms.Form):
    ncid = forms.CharField()

    def clean_ncid(self):
        return self.cleaned_data["ncid"].strip().upper()
