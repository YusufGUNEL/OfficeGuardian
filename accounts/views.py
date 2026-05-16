import json
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from django.views import View
from django.views.decorators.http import require_POST
from .forms import LoginForm, RegisterForm, ProfileForm, PasswordChangeCustomForm


class CustomLoginView(LoginView):
    form_class = LoginForm
    template_name = 'accounts/login.html'

    def get_redirect_url(self):
        return self.request.POST.get('next', self.request.GET.get('next', '/'))


class RegisterView(View):
    def get(self, request):
        form = RegisterForm()
        return render(request, 'accounts/register.html', {'form': form})

    def post(self, request):
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('/')
        return render(request, 'accounts/register.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('accounts:login')


@require_POST
@login_required
def toggle_theme(request):
    """Tema tercihini degistir (AJAX)."""
    try:
        data = json.loads(request.body)
        theme = data.get('theme', 'dark')
        if theme in ('dark', 'light'):
            request.user.theme = theme
            request.user.save(update_fields=['theme'])
            return JsonResponse({'status': 'ok', 'theme': theme})
    except (json.JSONDecodeError, Exception):
        pass
    return JsonResponse({'status': 'error'}, status=400)


@login_required
def profile_view(request):
    """Profil sayfasi."""
    password_form = PasswordChangeCustomForm(request.user)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'update_profile':
            form = ProfileForm(request.POST, instance=request.user)
            if form.is_valid():
                form.save()
                return redirect('accounts:profile')
        elif action == 'change_password':
            form = ProfileForm(instance=request.user)
            password_form = PasswordChangeCustomForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                return redirect('accounts:profile')
        else:
            form = ProfileForm(instance=request.user)
    else:
        form = ProfileForm(instance=request.user)

    return render(request, 'accounts/profile.html', {
        'form': form,
        'password_form': password_form,
    })
