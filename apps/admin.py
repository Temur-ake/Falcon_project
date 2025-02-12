from django.contrib.admin import register, ModelAdmin, StackedInline
from mptt.admin import DraggableMPTTAdmin

from apps.models import Category, Product, ProductImage, Tag, Review
from apps.models.orders import Order, OrderItem
from apps.models.user import SiteSettings


@register(Category)
class CategoryModelAdmin(DraggableMPTTAdmin, ModelAdmin):
    pass


@register(ProductImage)
class ProductImageModelAdmin(ModelAdmin):
    pass


@register(Tag)
class TagsModelAdmin(ModelAdmin):
    pass


@register(Review)
class ReviewModelAdmin(ModelAdmin):
    pass


class ReviewInline(StackedInline):
    model = Review
    extra = 1


class ProductImageInline(StackedInline):
    model = ProductImage
    extra = 1
    min_num = 1


@register(Product)
class ProductModelAdmin(ModelAdmin):
    inlines = [ProductImageInline, ReviewInline]


@register(Order)
class OrderModelAdmin(ModelAdmin):
    pass


@register(OrderItem)
class OrderItemsModelAdmin(ModelAdmin):
    pass


@register(SiteSettings)
class SiteSettingsModelAdmin(ModelAdmin):
    pass
