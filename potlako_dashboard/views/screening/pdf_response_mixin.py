import os
from django.conf import settings
from django.http import HttpResponse
from django.apps import apps as django_apps
from django.template.loader import get_template
from xhtml2pdf import pisa
from io import BytesIO
from django.contrib.staticfiles import finders
import posixpath
from edc_base.utils import get_utcnow


class UnsupportedMediaPathException(Exception):
    pass


class PdfResponseMixin(object, ):
    
    pdf_name = None
    pdf_template = None

    def get_pdf_name(self):
        return self.pdf_name
    
    def check_upload_dir_exists(self, upload_dir):
        file_path = 'media/%(upload_dir)s' % {'upload_dir': upload_dir}

        if not os.path.exists(file_path):
            os.makedirs(file_path)
        return file_path
    
    def handle_uploaded_file(self, context, model_obj=None, **kwargs):
        
        template = self.pdf_template
        
        self.upload_to = self.model_cls.file.field.upload_to
   
        upload_dir = self.check_upload_dir_exists(self.upload_to)
  
        output_filename = f'{upload_dir}{self.get_pdf_name()}.pdf'
        self.pdf = self.generate_pdf(
            template, output_filename=output_filename, context_dict=context)
        
        if model_obj:
            model_obj.file = f'{self.upload_to}{self.get_pdf_name()}.pdf'
            model_obj.save()

    def view_pdf(self, context,  **kwargs):
        template = self.pdf_template
        resp = HttpResponse(content_type='application/pdf')
        resp['Content-Disposition'] = 'attachment; filename="{0}.pdf"'.format(
            self.get_pdf_name())
        result = self.display_pdf(template, file_object=resp, context_dict=context)
        return result

    def fetch_resources(self, uri, rel):
        """
        Callback to allow xhtml2pdf/reportlab to retrieve Images,Stylesheets, etc
        @param uri: is the href attribute from the html link element.
        @param rel: gives a relative path, but it's not used here.
        """
    
        if uri.startswith("http://") or uri.startswith("https://"):
            return uri
    
        if settings.DEBUG:
            newpath = uri.replace(settings.STATIC_URL, "").replace(settings.MEDIA_URL, "")
            normalized_path = posixpath.normpath(newpath).lstrip('/')
            absolute_path = finders.find(normalized_path)
            if absolute_path:
                return absolute_path
    
        if settings.MEDIA_URL and uri.startswith(settings.MEDIA_URL):
            path = os.path.join(settings.MEDIA_ROOT,
                                uri.replace(settings.MEDIA_URL, ""))
        elif settings.STATIC_URL and uri.startswith(settings.STATIC_URL):
            path = os.path.join(settings.STATIC_ROOT,
                                uri.replace(settings.STATIC_URL, ""))
            if not os.path.exists(path):
                for d in settings.STATICFILES_DIRS:
                    path = os.path.join(d, uri.replace(settings.STATIC_URL, ""))
                    if os.path.exists(path):
                        break
        else:
            raise UnsupportedMediaPathException(
                                    'media urls must start with %s or %s' % (
                                    settings.MEDIA_URL, settings.STATIC_URL))
        return path
        
    def generate_pdf(self, template_src, file_object=None, output_filename=None, context_dict=None):
        """
            Uses the xhtml2pdf library to render a PDF to the passed file_object,
            from the given template name.
            @return: passed-in file object, filled with the actual PDF data.
            In case the passed in file object is none, it will return a BytesIO instance.
        """
        #open output file for writing (truncated binary)
        result_file = open(output_filename, "w+b")
        if not context_dict:
            context_dict = {}
    
        template = get_template(template_src)
     
        source_html = template.render(context_dict)
        # convert HTML to PDF
        pisa_status = pisa.CreatePDF(
                BytesIO(source_html.encode("UTF-8")),
                dest=result_file,
                link_callback=self.fetch_resources)
     
        # close output file
        result_file.close()
     
        return pisa_status.err
    
    def display_pdf(self, template_src, file_object=None, output_filename=None, context_dict=None):

        if not file_object:
            file_object = BytesIO()
        if not context_dict:
            context_dict = {}
        template = get_template(template_src)
      
        html = template.render(context_dict)
      
        pdf = pisa.pisaDocument(
            BytesIO(html.encode("UTF-8")), file_object, link_callback=self.fetch_resources)
        if not pdf.err:
            return HttpResponse(
                file_object.getvalue(), content_type='application/pdf')
        return None

    @property
    def model_cls(self):
        return django_apps.get_model(self.model)

    def model_obj(self, **kwargs):
        filter_options = self.filter_options(**kwargs)
        try:
            return self.model_cls.objects.get(**filter_options)
        except self.model_cls.DoesNotExist:
            return None

    def model_obj_set(self, model_obj):
        return []

    def filter_options(self, **kwargs):
        return {}
