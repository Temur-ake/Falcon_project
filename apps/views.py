from django.contrib.auth import logout, authenticate, login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.db.models import Sum, F, Q, Avg
from django.http import JsonResponse, HttpResponseRedirect, FileResponse
from django.shortcuts import redirect, get_object_or_404, render
from django.urls import reverse_lazy, reverse
from django.views import View
from django.views.generic import ListView, DetailView, UpdateView, CreateView, DeleteView

from apps.forms import UserRegisterModelForm, OrderCreateModelForm, ReviewCreateModelForm, CustomLoginForm
from apps.models import Product, Category, User, CartItem, Address, Review, SiteSettings, Favorite, Order, OrderItem
from apps.tasks import send_to_email
from apps.utils import make_pdf


# from django.core.cache import cache


class CategoryMixin:
    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        context['categories'] = Category.objects.all()
        return context


class ProductListView(CategoryMixin, ListView):
    queryset = Product.objects.all()
    template_name = 'apps/product/product-list.html'
    context_object_name = 'products'

    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        category_slug = self.request.GET.get('category')
        if tags_slug := self.request.GET.get('tag'):
            qs = qs.filter(tags__slug=tags_slug)
        elif category_slug:
            qs = qs.filter(category__slug=category_slug)
        if ordering := self.request.GET.get('sorting'):
            qs.order_by(ordering)
        if search := self.request.GET.get('search'):
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search) | Q(about__icontains=search))

        # and (self.request.user.has_pro or self.request.user.is_superuser or self.request.user.is_staff)
        if self.request.user.is_authenticated:
            return qs
        return qs.filter(is_premium=False)

    def get_context_data(self, *, object_list=None, **kwargs):
        ctx = super().get_context_data(object_list=object_list, **kwargs)
        avg_ratings = []
        blank_stars = []
        for product in ctx[self.context_object_name]:
            avg_rating = int(Review.objects.filter(product=product).aggregate(rating=Avg('rating'))['rating'] or 0)
            avg_ratings.append(avg_rating)
            blank_stars.append(5 - avg_rating)

        ctx['avg_ratings'] = avg_ratings
        ctx['blank_stars'] = blank_stars

        return ctx


class ProductDetailView(CategoryMixin, DetailView):
    queryset = Product.objects.all()
    template_name = 'apps/product/product-detail.html'
    context_object_name = 'product'

    # def get_context_data(self, *, object_list=None, **kwargs):
    #     ctx = super().get_context_data(object_list=object_list, **kwargs)
    #     avg_rating = int(Review.objects.filter(product=self.object).aggregate(rating=Avg('rating'))['rating'])
    #     ctx['avg_rating'] = avg_rating
    #     ctx['blank_star'] = 5 - avg_rating
    #
    #     return ctx


class ProductGridVIew(CategoryMixin, ListView):
    queryset = Product.objects.all()
    template_name = 'apps/product/product-grid.html'
    context_object_name = 'product'
    paginate_by = 10


class SettingsUpdateView(LoginRequiredMixin, CategoryMixin, UpdateView):
    queryset = User.objects.all()
    template_name = 'apps/auth/settings.html'
    fields = 'first_name', 'last_name', 'email'
    success_url = reverse_lazy('settings_page')

    def get_object(self, queryset=None):
        return self.request.user


class CustomLoginView(LoginView):
    form_class = CustomLoginForm
    template_name = 'apps/auth/login.html'
    redirect_authenticated_user = True
    next_page = reverse_lazy('list_view')

    def form_valid(self, form):
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        user = authenticate(self.request, username=username, password=password)
        if user is not None:
            login(self.request, user)
            return super().form_valid(form)
        else:
            form.add_error(None, 'Invalid username or password')
            return self.form_invalid(form)


class RegisterCreateView(CreateView):
    template_name = 'apps/auth/register.html'
    form_class = UserRegisterModelForm
    success_url = reverse_lazy('list_view')

    def form_valid(self, form):
        form.save()
        send_to_email.delay('Your account has been created', form.data['email'])
        return super().form_valid(form)

    def dispatch(self, request, *args, **kwargs):
        if self.request.user.is_authenticated:
            redirect_to = reverse_lazy('list_view')
            if redirect_to == self.request.path:
                raise ValueError(
                    "Redirection loop for authenticated user detected. Check that "
                    "your LOGIN_REDIRECT_URL doesn't point to a login page."
                )
            return HttpResponseRedirect(redirect_to)
        return super().dispatch(request, *args, **kwargs)


class LogoutView(View):
    def get(self, request, *args, **kwargs):
        logout(request)
        return redirect('list_view')


class ReviewCreateView(CategoryMixin, CreateView):
    model = Review
    form_class = ReviewCreateModelForm
    template_name = 'apps/product/product-detail.html'

    def get_success_url(self):
        return reverse_lazy('detail_view', kwargs={'pk': self.kwargs['pk']})


class CartListView(CategoryMixin, ListView):
    queryset = CartItem.objects.all()
    template_name = 'apps/shopping/shopping_cart.html'
    context_object_name = 'shopping_cart'

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)

        qs = self.get_queryset()

        context.update(
            **qs.aggregate(
                total_sum=Sum(F('quantity') * F('product__price') * (100 - F('product__discount')) / 100),
                total_count=Sum(F('quantity'))
            )
        )

        return context


def update_quantity(request, pk):
    if request.method == 'POST':
        product = get_object_or_404(CartItem, pk=pk)
        new_quantity = int(request.POST.get('quantity', 1))
        if new_quantity > 0:
            product.quantity = new_quantity
            product.save()

            total_sum = CartItem.objects.aggregate(
                total_sum=Sum(F('quantity') * F('product__price') * (100 - F('product__discount')) / 100)
            )['total_sum'] or 0

            total_count = CartItem.objects.aggregate(
                total_count=Sum('quantity')
            )['total_count'] or 0

            return JsonResponse({'new_quantity': new_quantity, 'total_sum': total_sum, 'total_count': total_count})
    return JsonResponse({'error': 'Invalid request'}, status=400)


class CartDeleteView(DeleteView):
    model = CartItem
    success_url = reverse_lazy('cart_page')


class AddToCartView(View):
    def get(self, request, pk, *args, **kwargs):
        product = get_object_or_404(Product, id=pk)
        cart_item, created = CartItem.objects.get_or_create(user=request.user, product=product)

        if not created:
            cart_item.quantity += 1
            cart_item.save()

        return redirect('cart_page')


class AddressCreateView(CategoryMixin, CreateView):
    model = Address
    template_name = 'apps/address/create_address.html'
    fields = 'city', 'street', 'zip_code', 'phone', 'full_name'
    context_object_name = 'create_address'
    success_url = reverse_lazy("checkout_page")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class AddressUpdateView(CategoryMixin, UpdateView):
    model = Address
    template_name = 'apps/address/update_address.html'
    fields = 'city', 'street', 'phone', 'zip_code'
    success_url = reverse_lazy('checkout_page')


class CheckoutListView(LoginRequiredMixin, CategoryMixin, ListView):
    template_name = 'apps/shopping/checkout.html'
    model = CartItem
    context_object_name = 'cart_items'

    def get_queryset(self):
        return super().get_queryset().filter(user=self.request.user)

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)

        qs = self.get_queryset()
        subtotal = qs.aggregate(
            subtotal=Sum(F('quantity') * F('product__price') * (100 - F('product__discount')) / 100)
        )['subtotal'] or 0.0
        shipping_cost = qs.aggregate(
            shipping_cost=Sum(F('product__shipping_cost'))
        )['shipping_cost'] or 0.0

        context.update({
            'subtotal': subtotal,
            'shipping_cost': shipping_cost,
            'addresses': Address.objects.filter(user=self.request.user)
        })

        site_settings = SiteSettings.objects.first()
        context['tax'] = site_settings.tax if site_settings else 0.0

        return context


class OrderListView(CategoryMixin, ListView):
    queryset = Order.objects.order_by('-created_at')
    template_name = 'apps/orders/order_list.html'
    context_object_name = 'orders'
    paginate_by = 10

    def get_queryset(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            return super().get_queryset()
        return super().get_queryset().filter(owner=self.request.user)

    def get_context_data(self, *, object_list=None, **kwargs):
        context = super().get_context_data(object_list=object_list, **kwargs)
        site_settings = SiteSettings.objects.first()
        context['tax'] = site_settings.tax if site_settings else 0.0
        return context


class OrderDetailView(LoginRequiredMixin, CategoryMixin, DetailView):
    model = Order
    template_name = 'apps/orders/order_details.html'
    context_object_name = 'order'

    def get_queryset(self):
        if self.request.user.is_staff or self.request.user.is_superuser:
            return super().get_queryset()
        return super().get_queryset().filter(owner=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        order = self.get_object()

        qs = OrderItem.objects.filter(order=order)

        subtotal = qs.aggregate(
            subtotal=Sum(F('quantity') * (F('product__price') * (100 - F('product__discount')) / 100)),
        )['subtotal'] or 0.0
        shipping_cost = qs.aggregate(
            shipping_cost=Sum(F('product__shipping_cost'))
        )['shipping_cost'] or 0.0

        context.update({
            'subtotal': subtotal,
            'shipping_cost': shipping_cost,
        })

        site_settings = SiteSettings.objects.first()
        context['tax'] = site_settings.tax if site_settings else 0.0

        return context


class OrderDeleteView(DeleteView):
    model = Order
    success_url = reverse_lazy('orders_list')


class OrderCreateView(LoginRequiredMixin, CategoryMixin, CreateView):
    model = Order
    template_name = 'apps/shopping/checkout.html'
    form_class = OrderCreateModelForm
    success_url = reverse_lazy('orders_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


# class CustomerListView(CategoryMixin, ListView):
#     model = User
#     template_name = 'apps/customer/customer_order_list.html'
#     paginate_by = 10
#     context_object_name = 'customers_list'
#
#     def get(self, request, *args, **kwargs):
#         if request.user.is_staff or request.user.is_superuser:
#             return super().get(request, *args, **kwargs)
#         return redirect('list_view')


class FavouriteView(LoginRequiredMixin, CategoryMixin, View):
    def get(self, request, pk, *args, **kwargs):
        obj, created = Favorite.objects.get_or_create(user=request.user, product_id=pk)
        if not created:
            obj.delete()
        referer = request.META.get('HTTP_REFERER')
        if referer:
            return redirect(referer)
        else:
            return redirect('product_detail', pk=pk)


class OrderPdfCreateView(View):
    def get(self, request, pk, *args, **kwargs):
        order = get_object_or_404(Order, pk=pk)
        if not order.pdf_file:
            make_pdf(order)
        # return FileResponse(order.pdf_file.open(), as_attachment=True)
        return FileResponse(order.pdf_file, as_attachment=True)
