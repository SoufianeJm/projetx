from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from .models import Resource, Mission
from .forms import ResourceForm, MissionForm

# Create your views here.

@login_required
def home(request):
    resources = Resource.objects.all()
    missions = Mission.objects.all()
    context = {
        'resources': resources,
        'missions': missions,
    }
    return render(request, 'billing/home.html', context)

# Resource CRUD Views
class ResourceCreateView(LoginRequiredMixin, CreateView):
    model = Resource
    form_class = ResourceForm
    template_name = 'billing/generic_form.html'
    success_url = reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Create New Resource'
        context['form_title'] = 'Add Resource'
        return context

class ResourceUpdateView(LoginRequiredMixin, UpdateView):
    model = Resource
    form_class = ResourceForm
    template_name = 'billing/generic_form.html'
    success_url = reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Update Resource'
        context['form_title'] = f"Edit Resource: {self.object.full_name}"
        return context

class ResourceDeleteView(LoginRequiredMixin, DeleteView):
    model = Resource
    template_name = 'billing/generic_confirm_delete.html'
    success_url = reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Delete Resource'
        context['item_name'] = self.object.full_name
        return context

# Mission CRUD Views
class MissionCreateView(LoginRequiredMixin, CreateView):
    model = Mission
    form_class = MissionForm
    template_name = 'billing/generic_form.html'
    success_url = reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Create New Mission'
        context['form_title'] = 'Add Mission'
        return context

class MissionUpdateView(LoginRequiredMixin, UpdateView):
    model = Mission
    form_class = MissionForm
    template_name = 'billing/generic_form.html'
    success_url = reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Update Mission'
        context['form_title'] = f"Edit Mission: {self.object.otp_l2}"
        return context

class MissionDeleteView(LoginRequiredMixin, DeleteView):
    model = Mission
    template_name = 'billing/generic_confirm_delete.html'
    success_url = reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Delete Mission'
        context['item_name'] = self.object.otp_l2
        return context
