from datetime import datetime
from django import forms

from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from django.forms import ModelForm, CharField, ModelChoiceField
from django_recaptcha.fields import ReCaptchaField

from apps.models import User, Address, CartItem, Review, Product
from apps.models.orders import Order, CreditCard, OrderItem


class UserRegisterModelForm(ModelForm):
    password2 = CharField(max_length=128)

    class Meta:
        model = User
        fields = 'first_name', 'last_name', 'email', 'username', 'password', 'password2'

    def clean_password2(self):
        password = self.cleaned_data.get("password")
        password2 = self.cleaned_data.get("password2")
        if password and password2 and password != password2:
            raise ValidationError
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        user.save()
        return user


class OrderCreateModelForm(ModelForm):
    address = ModelChoiceField(queryset=Address.objects.all())
    owner = ModelChoiceField(queryset=User.objects.all(), required=False)

    class Meta:
        model = Order
        fields = 'payment_method', 'address', 'owner'

    def save(self, commit=True):
        obj: Order = super().save(commit)

        if commit and obj.payment_method == 'credit_card':
            cvv = self.data.get('cvv')
            month, year = map(int, self.data.get('expire_date').split('/'))
            expire_date = datetime(year + 2000, month, 1).date()
            number = self.data.get('number')
            CreditCard.objects.create(
                owner=obj.owner,
                order=obj,
                cvv=cvv,
                expire_date=expire_date,
                number=number
            )

        for cart_item in obj.owner.cartitem_set.all():
            OrderItem.objects.create(order=obj,
                                     quantity=cart_item.quantity,
                                     product=cart_item.product)
            cart_item.product.quantity -= cart_item.quantity
            cart_item.product.save()
        CartItem.objects.filter(user=obj.owner).delete()
        return obj


class ReviewCreateModelForm(ModelForm):
    # product = ModelChoiceField(queryset=Product.objects.all())

    class Meta:
        model = Review
        fields = ['name', 'review_text', 'email_address', "product", "user"]


class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(max_length=254)
    password = forms.CharField(widget=forms.PasswordInput)
    captcha = ReCaptchaField()
