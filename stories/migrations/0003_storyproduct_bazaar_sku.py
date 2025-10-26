from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stories", "0002_storyproduct_story_product"),
    ]

    operations = [
        migrations.AddField(
            model_name="storyproduct",
            name="bazaar_sku",
            field=models.CharField(blank=True, default="", help_text="SKU ثبت‌شده در کافه‌بازار", max_length=120),
        ),
    ]
