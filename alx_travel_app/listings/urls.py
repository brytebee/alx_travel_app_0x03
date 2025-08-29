from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from . import views

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'listings', views.ListingViewSet, basename='listing')
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'locations', views.LocationViewSet, basename='location')
router.register(r'reviews', views.ReviewViewSet, basename='review')
router.register(r'bookings', views.BookingViewSet, basename='booking')

# The API URLs are now determined automatically by the router
urlpatterns = [
    path('', include(router.urls)),
    
    # Additional custom endpoints
    path('listings/<uuid:listing_id>/reviews/', views.ListingReviewsView.as_view(), name='listing-reviews'),
    path('listings/<uuid:listing_id>/favorite/', views.ToggleFavoriteView.as_view(), name='toggle-favorite'),
    path('listings/<uuid:listing_id>/book/', views.CreateBookingView.as_view(), name='create-booking'),
    path('search/', views.SearchListingsView.as_view(), name='search-listings'),
    path('my-listings/', views.MyListingsView.as_view(), name='my-listings'),
    path('my-bookings/', views.MyBookingsView.as_view(), name='my-bookings'),
    path('my-favorites/', views.MyFavoritesView.as_view(), name='my-favorites'),

    # Swagger URLs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # Payment
    path('payments/initiate/', views.initiate_payment, name='initiate_payment'),
    path('payments/verify/<str:transaction_id>/', views.verify_payment, name='verify_payment'),
    path('payments/callback/', views.payment_callback, name='payment_callback'),
    path('payments/status/<uuid:payment_id>/', views.payment_status, name='payment_status'),
]

# URL patterns for the app
app_name = 'listings'