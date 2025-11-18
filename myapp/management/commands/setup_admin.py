from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from myapp.models import CustomUser

class Command(BaseCommand):
    help = 'Create initial admin user for ArjenSystem'

    def handle(self, *args, **options):
        User = get_user_model()
        
        # Check if admin user already exists
        if User.objects.filter(username='admin').exists():
            self.stdout.write(
                self.style.WARNING('Admin user already exists')
            )
            return
        
        # Create admin user
        admin_user = User.objects.create_user(
            username='admin',
            email='admin@arjenappliances.com',
            password='admin123',
            full_name='System Administrator',
            role='admin',
            status='active'
        )
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()
        
        self.stdout.write(
            self.style.SUCCESS('Successfully created admin user')
        )
        self.stdout.write('Username: admin')
        self.stdout.write('Password: admin123')
        self.stdout.write('Role: admin')
