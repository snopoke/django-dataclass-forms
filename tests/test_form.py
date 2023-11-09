import dataclasses
from datetime import date, datetime, time
from typing import List

import pytest
from django.forms import fields, modelform_factory

from django_dataclass_forms import DataclassForm


@pytest.mark.parametrize(
    ("dataclass_field", "form_field"),
    [
        (("string", str), fields.CharField),
        (("integer", int), fields.IntegerField),
        (("float", float), fields.FloatField),
        (("boolean", bool), fields.BooleanField),
        (("date", date), fields.DateField),
        (("datetime", datetime), fields.DateTimeField),
        (("time", time), fields.TimeField),
    ],
)
def test_form_basics(dataclass_field, form_field):
    d_class = dataclasses.make_dataclass("DataclassFormTest", [dataclass_field])
    form = modelform_factory(d_class, form=DataclassForm, fields="__all__")
    assert list(form.base_fields) == [dataclass_field[0]]
    assert form.base_fields[dataclass_field[0]].__class__ == form_field


def test_form_field_classes():
    d_class = dataclasses.make_dataclass("DataclassFormTest", [("to", List[str])])
    form = modelform_factory(d_class, form=DataclassForm, fields="__all__", field_classes={"to": fields.EmailField})
    assert list(form.base_fields) == ["to"]
    assert form.base_fields["to"].__class__ == fields.EmailField


def test_formfield_callback():
    d_class = dataclasses.make_dataclass("DataclassFormTest", [("to", str)])
    form = modelform_factory(
        d_class, form=DataclassForm, fields="__all__", formfield_callback=lambda f: fields.EmailField()
    )
    assert list(form.base_fields) == ["to"]
    assert form.base_fields["to"].__class__ == fields.EmailField
