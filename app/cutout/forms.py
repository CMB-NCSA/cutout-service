from django import forms
from django.core.exceptions import ValidationError
import pandas
import io
from .log import get_logger
logger = get_logger(__name__)


def validate_csv(value):
    try:
        df = pandas.read_csv(io.StringIO(value), comment='#', skipinitialspace=True)
        df.to_csv(index=False)
        assert len(df.RA.values)
        assert len(df.DEC.values)
        assert len(df.RA.values) == len(df.DEC.values)
        return True
    except Exception as err:
        logger.error(err)
        raise ValidationError(str(err))


class CutoutForm(forms.Form):
    job_name = forms.CharField(label="Job name", max_length=100, initial='',
                               required=False,
                               widget=forms.TextInput(attrs={
                                   'placeholder': 'Job name',
                                   'style': 'width: 300px;',
                                   'class': 'form-control'}))
    job_description = forms.CharField(label="Job description", max_length=200,
                                      initial='',
                                      required=False,
                                      widget=forms.TextInput(attrs={
                                          'placeholder': 'Job description',
                                          'style': 'width: 300px;',
                                          'class': 'form-control'}))
    xsize = forms.IntegerField(label="X Size", initial=1, required=False,
                               widget=forms.TextInput(attrs={
                                   'placeholder': '1',
                                   'style': 'width: 300px;',
                                   'class': 'form-control'}))
    ysize = forms.IntegerField(label="Y Size", initial=1, required=False,
                               widget=forms.TextInput(attrs={
                                   'placeholder': '1',
                                   'style': 'width: 300px;',
                                   'class': 'form-control'}))
    tag = forms.ChoiceField(label="Survey",
                            choices=[
                                ("Y6A2", "DES"),  
                                ("DR3", "DECA"),
                            ],
                            widget=forms.RadioSelect,
                            initial="Y6A2",
                            required=False,)
    bands = forms.MultipleChoiceField(choices=[('g','g'), ('r','r'), ('i','i'), ('z','z'), ('Y','Y')],
                                    widget=forms.CheckboxSelectMultiple,
                                    required=False)
    # colorset = forms.CharField(label="Color set", max_length=30, initial='i r g')
    input_csv = forms.CharField(label="Coordinates", required=False,
                                widget=forms.Textarea(attrs={
                                    'placeholder': 'RA,DEC,XSIZE,YSIZE,ID\n',
                                    'style': 'width: 300px;',
                                    'class': 'form-control'}),
                                validators=[validate_csv],
                                initial=('''RA,DEC,XSIZE,YSIZE,ID\n'''
                                         '''0.29782658,0.029086056,3,3,1111\n'''
                                         '''1.0319154,0.026711725,3,3,1111\n'''))
    upload_csv = forms.FileField(
        label="Upload CSV",
        required=False,
        widget=forms.FileInput(attrs={'accept': '.csv'})
    )
    
    
