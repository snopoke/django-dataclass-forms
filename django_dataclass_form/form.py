import dataclasses
from datetime import date, datetime, time

from django.core.exceptions import FieldError, ImproperlyConfigured
from django.forms import ALL_FIELDS, fields
from django.forms.forms import BaseForm, DeclarativeFieldsMetaclass
from django.forms.utils import ErrorList


def form_field_for_dataclass_field(dataclass_field):
    if dataclass_field.type is str:
        return fields.CharField
    elif dataclass_field.type is int:
        return fields.IntegerField
    elif dataclass_field.type is float:
        return fields.FloatField
    elif dataclass_field.type is bool:
        return fields.BooleanField
    elif dataclass_field.type is date:
        return fields.DateField
    elif dataclass_field.type is datetime:
        return fields.DateTimeField
    elif dataclass_field.type is time:
        return fields.TimeField
    else:
        raise ImproperlyConfigured(f"Unsupported type {dataclass_field.type} for field {dataclass_field.name}")


def fields_for_dataclass(
    dataclass_type,
    fields=None,
    exclude=None,
    widgets=None,
    formfield_callback=None,
    labels=None,
    help_texts=None,
    error_messages=None,
    field_classes=None,
):
    """
    Return a dictionary containing form fields for the given model.

    ``fields`` is an optional list of field names. If provided, return only the
    named fields.

    ``exclude`` is an optional list of field names. If provided, exclude the
    named fields from the returned fields, even if they are listed in the
    ``fields`` argument.

    ``widgets`` is a dictionary of model field names mapped to a widget.

    ``formfield_callback`` is a callable that takes a model field and returns
    a form field.

    ``labels`` is a dictionary of model field names mapped to a label.

    ``help_texts`` is a dictionary of model field names mapped to a help text.

    ``error_messages`` is a dictionary of model field names mapped to a
    dictionary of error messages.

    ``field_classes`` is a dictionary of model field names mapped to a form
    field class.

    ``apply_limit_choices_to`` is a boolean indicating if limit_choices_to
    should be applied to a field's queryset.
    """
    field_dict = {}
    ignored = []

    dataclass_fields = dataclasses.fields(dataclass_type)
    for f in dataclass_fields:
        if fields is not None and f.name not in fields:
            continue
        if exclude and f.name in exclude:
            continue

        kwargs = {}
        if widgets and f.name in widgets:
            kwargs["widget"] = widgets[f.name]
        if labels and f.name in labels:
            kwargs["label"] = labels[f.name]
        if help_texts and f.name in help_texts:
            kwargs["help_text"] = help_texts[f.name]
        if error_messages and f.name in error_messages:
            kwargs["error_messages"] = error_messages[f.name]
        if field_classes and f.name in field_classes:
            kwargs["form_class"] = field_classes[f.name]

        if formfield_callback is None:
            formfield = form_field_for_dataclass_field(f)(**kwargs)
        elif not callable(formfield_callback):
            raise TypeError("formfield_callback must be a function or callable")
        else:
            formfield = formfield_callback(f, **kwargs)

        if formfield:
            field_dict[f.name] = formfield
        else:
            ignored.append(f.name)
    if fields:
        field_dict = {f: field_dict.get(f) for f in fields if (not exclude or f not in exclude) and f not in ignored}
    return field_dict


class DataclassFormOptions:
    def __init__(self, options=None):
        self.model = getattr(options, "model", None)
        self.fields = getattr(options, "fields", None)
        self.exclude = getattr(options, "exclude", None)
        self.widgets = getattr(options, "widgets", None)
        self.labels = getattr(options, "labels", None)
        self.help_texts = getattr(options, "help_texts", None)
        self.error_messages = getattr(options, "error_messages", None)
        self.field_classes = getattr(options, "field_classes", None)
        self.formfield_callback = getattr(options, "formfield_callback", None)


class DataclassFormMetaclass(DeclarativeFieldsMetaclass):
    def __new__(mcs, name, bases, attrs):
        new_class = super().__new__(mcs, name, bases, attrs)

        if bases == (BaseDataclassForm,):
            return new_class

        opts = new_class._meta = DataclassFormOptions(getattr(new_class, "Meta", None))

        # We check if a string was passed to `fields` or `exclude`,
        # which is likely to be a mistake where the user typed ('foo') instead
        # of ('foo',)
        for opt in ["fields", "exclude"]:
            value = getattr(opts, opt)
            if isinstance(value, str) and value != ALL_FIELDS:
                msg = "%(model)s.Meta.%(opt)s cannot be a string. " "Did you mean to type: ('%(value)s',)?" % {
                    "model": new_class.__name__,
                    "opt": opt,
                    "value": value,
                }
                raise TypeError(msg)

        if opts.model:
            if opts.fields == ALL_FIELDS:
                # Sentinel for fields_for_dataclass to indicate "get the list of
                # fields from the model"
                opts.fields = None

            fields = fields_for_dataclass(
                opts.model,
                opts.fields,
                opts.exclude,
                opts.widgets,
                opts.formfield_callback,
                opts.labels,
                opts.help_texts,
                opts.error_messages,
                opts.field_classes,
            )

            # make sure opts.fields doesn't specify an invalid field
            none_fields = {k for k, v in fields.items() if not v}
            missing_fields = none_fields.difference(new_class.declared_fields)
            if missing_fields:
                message = "Unknown field(s) (%s) specified for %s"
                message %= (", ".join(missing_fields), opts.model.__name__)
                raise FieldError(message)
            # Override default model fields with any custom declared ones
            # (plus, include all the other declared fields).
            fields.update(new_class.declared_fields)
        else:
            fields = new_class.declared_fields

        new_class.base_fields = fields

        return new_class


def dataclass_to_dict(instance, fields=None, exclude=None):
    """
    Return a dict containing the data in ``instance`` suitable for passing as
    a Form's ``initial`` keyword argument.

    ``fields`` is an optional list of field names. If provided, return only the
    named.

    ``exclude`` is an optional list of field names. If provided, exclude the
    named from the returned dict, even if they are listed in the ``fields``
    argument.
    """
    instance_data = dataclasses.asdict(instance)
    data = {}
    for field_name in instance_data:
        if fields is not None and field_name not in fields:
            continue
        if exclude and field_name in exclude:
            continue
        data[field_name] = instance_data[field_name]
    return data


class BaseDataclassForm(BaseForm):
    def __init__(
        self,
        data=None,
        files=None,
        auto_id="id_%s",
        prefix=None,
        initial=None,
        error_class=ErrorList,
        label_suffix=None,
        empty_permitted=False,
        instance=None,
        use_required_attribute=None,
        renderer=None,
    ):
        opts = self._meta
        if opts.model is None:
            raise ValueError("DataclassForm has no model specified.")
        self.instance = instance
        object_data = {}
        if instance is not None:
            object_data = dataclass_to_dict(instance, opts.fields, opts.exclude)
        # if initial was provided, it should override the values from instance
        if initial is not None:
            object_data.update(initial)
        # self._validate_unique will be set to True by BaseModelForm.clean().
        # It is False by default so overriding self.clean() and failing to call
        # super will stop validate_unique from being called.
        self._validate_unique = False
        super().__init__(
            data,
            files,
            auto_id,
            prefix,
            object_data,
            error_class,
            label_suffix,
            empty_permitted,
            use_required_attribute=use_required_attribute,
            renderer=renderer,
        )

    def _post_clean(self):
        try:
            self._get_instance()
        except Exception:
            # TODO
            # self._update_errors(e)
            raise

    def _get_instance(self):
        if self.instance:
            return dataclasses.replace(self.instance, **self.cleaned_data)
        else:
            return self._meta.model(**self.cleaned_data)

    def save(self):
        if self.errors:
            raise ValueError("The %s could not be created because the data didn't validate." % self.instance.__name__)

        return self._get_instance()


class DataclassForm(BaseDataclassForm, metaclass=DataclassFormMetaclass):
    pass
