from django.shortcuts import redirect


class VendorPortalMiddleware:
    """
    Redirects authenticated vendor users away from the Django admin
    to their dedicated vendor portal at /vendor/.
    Login and logout paths are always permitted so the flow works correctly.
    """

    ALLOWED_ADMIN_PATHS = ("/admin/login/", "/admin/logout/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and request.path.startswith("/admin/")
            and not any(request.path.startswith(p) for p in self.ALLOWED_ADMIN_PATHS)
        ):
            profile = getattr(request.user, "profile", None)
            if profile and profile.role == "vendor":
                return redirect("/vendor/")
            if profile and profile.role == "junior_superuser":
                return redirect("/review/")

        return self.get_response(request)
