from django.db import migrations


def copy_items(apps, schema_editor):
    """Catch any order placed since 0022 that still has no item row."""
    OrderRequest = apps.get_model("main", "OrderRequest")
    OrderItem = apps.get_model("main", "OrderItem")
    for order in OrderRequest.objects.all():
        if not OrderItem.objects.filter(order=order).exists():
            OrderItem.objects.create(
                order=order,
                item_description=order.item_description,
                color=order.color,
                length=order.length,
                gsm=order.gsm,
                quantity=order.quantity,
                position=0,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0022_copy_order_items'),
    ]

    operations = [
        migrations.RunPython(copy_items, migrations.RunPython.noop),
        migrations.RemoveField(model_name='orderrequest', name='color'),
        migrations.RemoveField(model_name='orderrequest', name='gsm'),
        migrations.RemoveField(model_name='orderrequest',
                               name='item_description'),
        migrations.RemoveField(model_name='orderrequest', name='length'),
        migrations.RemoveField(model_name='orderrequest', name='quantity'),
    ]
