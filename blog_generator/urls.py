from django.urls import path
from . import views

urlpatterns = [
     path('', views.index, name='index'),
     path('login', views.user_login, name='login'),
     path('logout', views.user_logout, name='logout'),
     path('signup', views.user_signup, name='signup'),
     path('generate-blog', views.generate_blog, name='generate_blog'),
     path('blog-posts', views.blog_posts, name='blog_posts'),
     path('blog-posts/<int:post_id>', views.blog_posts_id, name='blog_posts_id'),
]
