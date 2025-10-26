from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("stories", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="StoryProduct",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                ("uuid", models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("title", models.CharField(max_length=120)),
                ("slug", models.SlugField(blank=True, max_length=64, unique=True)),
                ("description", models.TextField(blank=True)),
                ("coin_price", models.PositiveIntegerField()),
                ("is_active", models.BooleanField(default=True)),
                ("features", models.JSONField(blank=True, default=list)),
                ("display_order", models.PositiveIntegerField(default=0)),
            ],
            options={
                "verbose_name": "Story product",
                "verbose_name_plural": "Story products",
                "ordering": ("display_order", "title"),
            },
        ),
        migrations.AddIndex(
            model_name="storyproduct",
            index=models.Index(fields=("is_active", "display_order"), name="stories_storyproduct_active_order_idx"),
        ),
        migrations.AddField(
            model_name="story",
            name="product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="stories",
                to="stories.storyproduct",
            ),
        ),
        migrations.AddIndex(
            model_name="story",
            index=models.Index(fields=("product", "plan_source"), name="story_product_plan_idx"),
        ),
    ]
