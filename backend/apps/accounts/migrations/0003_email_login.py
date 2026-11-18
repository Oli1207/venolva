from django.db import migrations, models


def purge_codes(apps, schema_editor):
    apps.get_model("accounts", "OtpCode").objects.all().delete()  # anciens codes liés à un numéro : inutilisables


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_initial")]

    operations = [
        migrations.RunPython(purge_codes, migrations.RunPython.noop),
        migrations.RenameField("otpcode", "phone", "email"),
        migrations.AlterField("otpcode", "email", models.EmailField(db_index=True, max_length=254)),
        migrations.AddField("user", "email", models.EmailField(blank=True, max_length=254, null=True, unique=True)),
        migrations.AlterField("user", "phone", models.CharField(blank=True, max_length=14, null=True, unique=True)),
    ]
