###############################################################################
#
# Worksheet - A class for writing the Excel XLSX Worksheet file.
#
# Copyright 2013, John McNamara, jmcnamara@cpan.org
#

# Standard packages.
import re
import datetime
import tempfile
import codecs
import os
from warnings import warn
from collections import defaultdict
from collections import namedtuple

# For compatibility between Python 2 and 3.
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

# Package imports.
from . import xmlwriter
from .format import Format
from .drawing import Drawing
from .xmlwriter import XMLwriter
from .utility import xl_rowcol_to_cell
from .utility import xl_cell_to_rowcol
from .utility import xl_col_to_name
from .utility import xl_range
from .utility import xl_color


###############################################################################
#
# Decorator functions.
#
###############################################################################
def convert_cell_args(method):
    """
    Decorator function to convert A1 notation in cell method calls
    to the default row/col notation.

    """
    def cell_wrapper(self, *args, **kwargs):

        try:
            # First arg is an int, default to row/col notation.
            if len(args):
                int(args[0])
            return method(self, *args, **kwargs)
        except ValueError:
            # First arg isn't an int, convert to A1 notation.
            new_args = list(xl_cell_to_rowcol(args[0]))
            new_args.extend(args[1:])
            return method(self, *new_args, **kwargs)

    return cell_wrapper


def convert_range_args(method):
    """
    Decorator function to convert A1 notation in range method calls
    to the default row/col notation.

    """
    def cell_wrapper(self, *args, **kwargs):

        try:
            # First arg is an int, default to row/col notation.
            if len(args):
                int(args[0])
            return method(self, *args, **kwargs)
        except ValueError:
            # First arg isn't an int, convert to A1 notation.
            if ':' in args[0]:
                cell_1, cell_2 = args[0].split(':')
                row_1, col_1 = xl_cell_to_rowcol(cell_1)
                row_2, col_2 = xl_cell_to_rowcol(cell_2)
            else:
                row_1, col_1 = xl_cell_to_rowcol(args[0])
                row_2, col_2 = row_1, col_1

            new_args = [row_1, col_1, row_2, col_2]
            new_args.extend(args[1:])
            return method(self, *new_args, **kwargs)

    return cell_wrapper


def convert_column_args(method):
    """
    Decorator function to convert A1 notation in columns method calls
    to the default row/col notation.

    """
    def column_wrapper(self, *args, **kwargs):

        try:
            # First arg is an int, default to row/col notation.
            if len(args):
                int(args[0])
            return method(self, *args, **kwargs)
        except ValueError:
            # First arg isn't an int, convert to A1 notation.
            cell_1, cell_2 = [col + '1' for col in args[0].split(':')]
            _, col_1 = xl_cell_to_rowcol(cell_1)
            _, col_2 = xl_cell_to_rowcol(cell_2)
            new_args = [col_1, col_2]
            new_args.extend(args[1:])
            return method(self, *new_args, **kwargs)

    return column_wrapper


###############################################################################
#
# Named tuples used for cell types.
#
###############################################################################
cell_string_tuple = namedtuple('String', 'string, format')
cell_number_tuple = namedtuple('Number', 'number, format')
cell_blank_tuple = namedtuple('Blank', 'format')
cell_formula_tuple = namedtuple('Formula', 'formula, format, value')
cell_arformula_tuple = namedtuple('ArrayFormula',
                                  'formula, format, value, range')


###############################################################################
#
# Worksheet Class definition.
#
###############################################################################
class Worksheet(xmlwriter.XMLwriter):
    """
    A class for writing the Excel XLSX Worksheet file.

    """

    ###########################################################################
    #
    # Public API.
    #
    ###########################################################################

    def __init__(self):
        """
        Constructor.

        """

        super(Worksheet, self).__init__()

        self.name = None
        self.index = None
        self.str_table = None
        self.palette = None
        self.optimization = 0
        self.tmpdir = None

        self.ext_sheets = []
        self.fileclosed = 0
        self.excel_version = 2007

        self.xls_rowmax = 1048576
        self.xls_colmax = 16384
        self.xls_strmax = 32767
        self.dim_rowmin = None
        self.dim_rowmax = None
        self.dim_colmin = None
        self.dim_colmax = None

        self.colinfo = []
        self.selections = []
        self.hidden = 0
        self.active = 0
        self.tab_color = 0

        self.panes = []
        self.active_pane = 3
        self.selected = 0

        self.page_setup_changed = 0
        self.paper_size = 0
        self.orientation = 1

        self.print_options_changed = 0
        self.hcenter = 0
        self.vcenter = 0
        self.print_gridlines = 0
        self.screen_gridlines = 1
        self.print_headers = 0

        self.header_footer_changed = 0
        self.header = ''
        self.footer = ''

        self.margin_left = 0.7
        self.margin_right = 0.7
        self.margin_top = 0.75
        self.margin_bottom = 0.75
        self.margin_header = 0.3
        self.margin_footer = 0.3

        self.repeat_row_range = ''
        self.repeat_col_range = ''
        self.print_area_range = ''

        self.page_order = 0
        self.black_white = 0
        self.draft_quality = 0
        self.print_comments = 0
        self.page_start = 0

        self.fit_page = 0
        self.fit_width = 0
        self.fit_height = 0

        self.hbreaks = []
        self.vbreaks = []

        self.protect_options = {}
        self.set_cols = {}
        self.set_rows = defaultdict(dict)

        self.zoom = 100
        self.zoom_scale_normal = 1
        self.print_scale = 100
        self.is_right_to_left = 0
        self.show_zeros = 1
        self.leading_zeros = 0

        self.outline_row_level = 0
        self.outline_col_level = 0
        self.outline_style = 0
        self.outline_below = 1
        self.outline_right = 1
        self.outline_on = 1
        self.outline_changed = 0

        self.default_row_height = 15
        self.default_row_zeroed = 0

        self.names = {}
        self.write_match = []
        self.table = defaultdict(dict)
        self.merge = []
        self.row_spans = {}

        self.has_vml = 0
        self.has_comments = 0
        self.comments = defaultdict(dict)
        self.comments_array = []
        self.comments_author = ''
        self.comments_visible = 0
        self.vml_shape_id = 1024
        self.buttons_array = []

        self.autofilter_area = ''
        self.autofilter_ref = None
        self.filter_range = []
        self.filter_on = 0
        self.filter_range = []
        self.filter_cols = {}
        self.filter_type = {}

        self.col_sizes = {}
        self.row_sizes = {}
        self.col_formats = {}
        self.col_size_changed = 0
        self.row_size_changed = 0

        self.last_shape_id = 1
        self.rel_count = 0
        self.hlink_count = 0
        self.hlink_refs = []
        self.external_hyper_links = []
        self.external_drawing_links = []
        self.external_comment_links = []
        self.external_vml_links = []
        self.external_table_links = []
        self.drawing_links = []
        self.charts = []
        self.images = []
        self.tables = []
        self.sparklines = []
        self.shapes = []
        self.shape_hash = {}
        self.drawing = 0

        self.rstring = ''
        self.previous_row = 0

        self.validations = []
        self.cond_formats = {}
        self.dxf_priority = 1
        self.is_chartsheet = 0
        self.page_view = 0

        self.vba_codename = None

        self.date_1904 = False
        self.epoch = datetime.datetime(1899, 12, 31)
        self.hyperlinks = defaultdict(dict)

    @convert_cell_args
    def write(self, row, col, *args):
        """
        Write data to a worksheet cell by calling the appropriate write_*()
        method based on the type of data being passed.

        Args:
            row:     The cell row (zero indexed).
            col:     The cell column (zero indexed).
            token:   Cell data.
            format:  An optional cell Format object.
            options: Any options to pass to sub function.

        Returns:
             0:    Success.
            -1:    Row or column is out of worksheet bounds.
            other: Return value of called method.

        """
        # Check the number of args passed.
        if not len(args):
            raise TypeError("write() takes at least 4 arguments (3 given)")

        # The first arg should be the token for all write calls.
        token = args[0]

        # Convert None to an empty string and thus a blank cell.
        if token is None:
            token = ''

        # Check for a datetime object.
        if self._is_supported_datetime(token):
            return self.write_datetime(row, col, *args)

        # Then check if the token to write is a number.
        try:
            float(token)
            return self.write_number(row, col, *args)
        except ValueError:
            # Not a number. Continue to the checks below.
            pass

        # Map the data to the appropriate write_*() method.
        if token == '':
            return self.write_blank(row, col, *args)
        elif token.startswith('='):
            return self.write_formula(row, col, *args)
        elif token.startswith('{') and token.endswith('}'):
            return self.write_formula(row, col, *args)
        elif re.match('[fh]tt?ps?://', token):
            return self.write_url(row, col, *args)
        elif re.match('mailto:', token):
            return self.write_url(row, col, *args)
        elif re.match('(in|ex)ternal:', token):
            return self.write_url(row, col, *args)
        else:
            return self.write_string(row, col, *args)

    @convert_cell_args
    def write_string(self, row, col, string, cell_format=None):
        """
        Write a string to a worksheet cell.

        Args:
            row:    The cell row (zero indexed).
            col:    The cell column (zero indexed).
            string: Cell data. Str.
            format: An optional cell Format object.

        Returns:
            0:  Success.
            -1: Row or column is out of worksheet bounds.
            -2: String truncated to 32k characters.

        """
        str_error = 0

        # Check that row and col are valid and store max and min values.
        if self._check_dimensions(row, col):
            return -1

        # Check that the string is < 32767 chars.
        if len(string) > self.xls_strmax:
            string = string[:self.xls_strmax]
            str_error = -2

        # Write a shared string or an in-line string in optimisation mode.
        if self.optimization == 0:
            string_index = self.str_table._get_shared_string_index(string)
        else:
            string_index = string

        # Write previous row if in in-line string optimization mode.
        if self.optimization and row > self.previous_row:
            self._write_single_row(row)

        # Store the cell data in the worksheet data table.
        self.table[row][col] = cell_string_tuple(string_index, cell_format)

        return str_error

    @convert_cell_args
    def write_number(self, row, col, number, cell_format=None):
        """
        Write a number to a worksheet cell.

        Args:
            row:         The cell row (zero indexed).
            col:         The cell column (zero indexed).
            number:      Cell data. Int or float.
            cell_format: An optional cell Format object.

        Returns:
            0:  Success.
            -1: Row or column is out of worksheet bounds.

        """
        # TODO catch and re-raise exception if token isn't a number.
        number = float(number)

        # Check that row and col are valid and store max and min values.
        if self._check_dimensions(row, col):
            return -1

        # Write previous row if in in-line string optimization mode.
        if self.optimization and row > self.previous_row:
            self._write_single_row(row)

        # Store the cell data in the worksheet data table.
        self.table[row][col] = cell_number_tuple(number, cell_format)

        return 0

    @convert_cell_args
    def write_blank(self, row, col, blank, cell_format=None):
        """
        Write a blank cell with formatting to a worksheet cell. The blank
        token is ignored and the format only is written to the cell.

        Args:
            row:         The cell row (zero indexed).
            col:         The cell column (zero indexed).
            blank:       Any value. It is ignored.
            cell_format: An optional cell Format object.

        Returns:
            0:  Success.
            -1: Row or column is out of worksheet bounds.

        """
        # Don't write a blank cell unless it has a format.
        if cell_format is None:
            return 0

        # Check that row and col are valid and store max and min values.
        if self._check_dimensions(row, col):
            return -1

        # Write previous row if in in-line string optimization mode.
        if self.optimization and row > self.previous_row:
            self._write_single_row(row)

        # Store the cell data in the worksheet data table.
        self.table[row][col] = cell_blank_tuple(cell_format)

        return 0

    @convert_cell_args
    def write_formula(self, row, col, formula, cell_format=None, value=0):
        """
        Write a formula to a worksheet cell.

        Args:
            row:         The cell row (zero indexed).
            col:         The cell column (zero indexed).
            formula:     Cell formula.
            cell_format: An optional cell Format object.
            value:       An optional value for the formula. Default is 0.

        Returns:
            0:  Success.
            -1: Row or column is out of worksheet bounds.

        """
        # Check that row and col are valid and store max and min values.
        if self._check_dimensions(row, col):
            return -1

        # Hand off array formulas.
        if formula.startswith('{') and formula.endswith('}'):
            return self.write_array_formula(row, col, row, col, formula,
                                            cell_format, value)

        # Remove the formula '=' sign if it exists.
        if formula.startswith('='):
            formula = formula.lstrip('=')

        # Write previous row if in in-line string optimization mode.
        if self.optimization and row > self.previous_row:
            self._write_single_row(row)

        # Store the cell data in the worksheet data table.
        self.table[row][col] = cell_formula_tuple(formula, cell_format, value)

        return 0

    @convert_range_args
    def write_array_formula(self, first_row, first_col, last_row, last_col,
                            formula, cell_format=None, value=0):
        """
        Write a formula to a worksheet cell.

        Args:
            first_row:    The first row of the cell range. (zero indexed).
            first_col:    The first column of the cell range.
            last_row:     The last row of the cell range. (zero indexed).
            last_col:     The last column of the cell range.
            formula:      Cell formula.
            cell_format:  An optional cell Format object.
            value:        An optional value for the formula. Default is 0.

        Returns:
            0:  Success.
            -1: Row or column is out of worksheet bounds.

        """

        # Swap last row/col with first row/col as necessary.
        if first_row > last_row:
            first_row, last_row = last_row, first_row
        if first_col > last_col:
            first_col, last_col = last_col, first_col

        # Check that row and col are valid and store max and min values
        if self._check_dimensions(last_row, last_col):
            return -1

        # Define array range
        if first_row == last_row and first_col == last_col:
            cell_range = xl_rowcol_to_cell(first_row, first_col)
        else:
            cell_range = (xl_rowcol_to_cell(first_row, first_col) + ':'
                          + xl_rowcol_to_cell(last_row, last_col))

        # Remove array formula braces and the leading =.
        if formula[0] == '{':
            formula = formula[1:]
        if formula[0] == '=':
            formula = formula[1:]
        if formula[-1] == '}':
            formula = formula[:-1]

        # Write previous row if in in-line string optimization mode.
        if self.optimization and first_row > self.previous_row:
            self._write_single_row(first_row)

        # Store the cell data in the worksheet data table.
        self.table[first_row][first_col] = cell_arformula_tuple(formula,
                                                                cell_format,
                                                                value,
                                                                cell_range)

        # Pad out the rest of the area with formatted zeroes.
        if not self.optimization:
            for row in range(first_row, last_row + 1):
                for col in range(first_col, last_col + 1):
                    if row != first_row or col != first_col:
                        self.write_number(row, col, 0, cell_format)

        return 0

    @convert_cell_args
    def write_datetime(self, row, col, date, cell_format):
        """
        Write a date or time to a worksheet cell.

        Args:
            row:         The cell row (zero indexed).
            col:         The cell column (zero indexed).
            date:        Date and/or time as a datetime object.
            cell_format: A cell Format object.

        Returns:
            0:  Success.
            -1: Row or column is out of worksheet bounds.

        """
        # Check that row and col are valid and store max and min values.
        if self._check_dimensions(row, col):
            return -1

        # Write previous row if in in-line string optimization mode.
        if self.optimization and row > self.previous_row:
            self._write_single_row(row)

        # Convert datetime to an Excel date.
        number = self._convert_date_time(date)

        # Store the cell data in the worksheet data table.
        self.table[row][col] = cell_number_tuple(number, cell_format)

        return 0

    # Write a hyperlink. This is comprised of two elements: the displayed
    # string and the non-displayed link. The displayed string is the same as
    # the link unless an alternative string is specified. The display string
    # is written using the write_string() method. Therefore the max characters
    # string limit applies.
    #
    # The hyperlink can be to a http, ftp, mail, internal sheet, or external
    # directory urls.
    @convert_cell_args
    def write_url(self, row, col, url, cell_format=None,
                  string=None, tip=None):
        """
        Write a hyperlink to a worksheet cell.

        Args:
            row:    The cell row (zero indexed).
            col:    The cell column (zero indexed).
            url:    Hyperlink url.
            format: An optional cell Format object.
            string: An optional display string for the hyperlink.
            tip:    An optional tooltip.
        Returns:
            0:  Success.
            -1: Row or column is out of worksheet bounds.
            -2: String longer than 32767 characters.
            -3: URL longer than Excel limit of 255 characters
            -4: Exceeds Excel limit of 65,530 urls per worksheet
        """
        # Default link type such as http://.
        link_type = 1

        # Remove the URI scheme from internal links.
        if re.match("internal:", url):
            url = url.replace('internal:', '')
            link_type = 2

        # Remove the URI scheme from external links.
        if re.match("external:", url):
            url = url.replace('external:', '')
            link_type = 3

        # Set the displayed string to the URL unless defined by the user.
        if string is None:
            string = url

        # For external links change the directory separator from Unix to Dos.
        if link_type == 3:
            url = url.replace('/', '\\')
            string = string.replace('/', '\\')

        # Strip the mailto header.
        string = string.replace('mailto:', '')

        # Check that row and col are valid and store max and min values
        if self._check_dimensions(row, col):
            return -1

        # Check that the string is < 32767 chars
        str_error = 0
        if len(string) > self.xls_strmax:
            warn("Ignoring URL since it exceeds Excel's string limit of "
                 "32767 characters")
            return -2

        # Copy string for use in hyperlink elements.
        url_str = string

        # External links to URLs and to other Excel workbooks have slightly
        # different characteristics that we have to account for.
        if link_type == 1:
            # Escape URL unless it looks already escaped.
            if not re.search('%[0-9a-fA-F]{2}', url):
                # Can't use url.quote() here because it doesn't match Excel.
                url = url.replace('%', '%25')
                url = url.replace('"', '%22')
                url = url.replace(' ', '%20')
                url = url.replace('<', '%3c')
                url = url.replace('>', '%3e')
                url = url.replace('[', '%5b')
                url = url.replace(']', '%5d')
                url = url.replace('^', '%5e')
                url = url.replace('`', '%60')
                url = url.replace('{', '%7b')
                url = url.replace('}', '%7d')

            # Ordinary URL style external links don't have a "location" string.
            url_str = None

        elif link_type == 3:

            # External Workbook links need to be modified into correct format.
            # The URL will look something like 'c:\temp\file.xlsx#Sheet!A1'.
            # We need the part to the left of the # as the URL and the part to
            # the right as the "location" string (if it exists).
            if re.search('#', url):
                url, url_str = url.split('#')
            else:
                url_str = None

            # Add the file:/// URI to the url if non-local.
            # Windows style "C:/" link. # Network share.
            if (re.match('\w:', url) or re.match(r'\\', url)):
                url = 'file:///' + url

            # Convert a .\dir\file.xlsx link to dir\file.xlsx.
            url = re.sub(r'^\.\\', '', url)

            # Treat as a default external link now the data has been modified.
            link_type = 1

        # Excel limits escaped URL to 255 characters.
        if len(url) > 255:
            warn("Ignoring URL '%s' > 255 characters since it exceeds "
                 "Excel's limit for URLS" % url)
            return -3

        # Check the limit of URLS per worksheet.
        self.hlink_count += 1

        if self.hlink_count > 65530:
            warn("Ignoring URL '%s' since it exceeds Excel's limit of "
                 "65,530 URLS per worksheet." % url)
            return -5

        # Write previous row if in in-line string optimization mode.
        if self.optimization == 1 and row > self.previous_row:
            self._write_single_row(row)

        # Write the hyperlink string.
        self.write_string(row, col, string, cell_format)

        # Store the hyperlink data in a separate structure.
        self.hyperlinks[row][col] = {
            'link_type': link_type,
            'url': url,
            'str': url_str,
            'tip': tip}

        return str_error

    @convert_cell_args
    def write_rich_string(self, row, col, *args):
        """
        Write a "rich" string with multiple formats to a worksheet cell.

        Args:
            row:          The cell row (zero indexed).
            col:          The cell column (zero indexed).
            string_parts: String and format pairs.
            cell_format:  Optional Format object.

        Returns:
            0:  Success.
            -1: Row or column is out of worksheet bounds.
            -2: String truncated to 32k characters.
            -3: 2 consecutive formats used.

        """
        tokens = list(args)
        cell_format = None
        str_length = 0
        string_index = 0

        # Check that row and col are valid and store max and min values
        if self._check_dimensions(row, col):
            return -1

        # If the last arg is a format we use it as the cell format.
        if isinstance(tokens[-1], Format):
            cell_format = tokens.pop()

        # Create a temp XMLWriter object and use it to write the rich string
        # XML to a string.
        fh = StringIO()
        self.rstring = XMLwriter()
        self.rstring._set_filehandle(fh)

        # Create a temp format with the default font for unformatted fragments.
        default = Format()

        # Convert list of format, string tokens to pairs of (format, string)
        # except for the first string fragment which doesn't require a default
        # formatting run. Use the default for strings without a leading format.
        fragments = []
        previous = 'format'
        pos = 0

        for token in (tokens):
            if not isinstance(token, Format):
                # Token is a string.
                if previous != 'format':
                    # If previous token wasn't a format add one before string.
                    fragments.append(default)
                    fragments.append(token)
                else:
                    # If previous token was a format just add the string.
                    fragments.append(token)

                # Keep track of actual string str_length.
                str_length += len(token)
                previous = 'string'
            else:
                # Can't allow 2 formats in a row.
                if previous == 'format' and pos > 0:
                    return -3

                # Token is a format object. Add it to the fragment list.
                fragments.append(token)
                previous = 'format'

            pos += 1

        # If the first token is a string start the <r> element.
        if not isinstance(fragments[0], Format):
            self.rstring._xml_start_tag('r')

        # Write the XML elements for the $format $string fragments.
        for token in (fragments):
            if isinstance(token, Format):
                # Write the font run.
                self.rstring._xml_start_tag('r')
                self._write_font(token)
            else:
                # Write the string fragment part, with whitespace handling.
                attributes = []

                if re.search('^\s', token) or re.search('\s$', token):
                    attributes.append(('xml:space', 'preserve'))

                self.rstring._xml_data_element('t', token, attributes)
                self.rstring._xml_end_tag('r')

        # Read the in-memory string.
        string = self.rstring.fh.getvalue()

        # Check that the string is < 32767 chars.
        if str_length > self.xls_strmax:
            return -2

        # Write a shared string or an in-line string in optimisation mode.
        if self.optimization == 0:
            string_index = self.str_table._get_shared_string_index(string)
        else:
            string_index = string

        # Write previous row if in in-line string optimization mode.
        if self.optimization and row > self.previous_row:
            self._write_single_row(row)

        # Store the cell data in the worksheet data table.
        self.table[row][col] = cell_string_tuple(string_index, cell_format)

        return 0

    @convert_cell_args
    def write_row(self, row, col, data, cell_format=None):
        """
        Write a row of data starting from (row, col).

        Args:
            row:    The cell row (zero indexed).
            col:    The cell column (zero indexed).
            data:   A list of tokens to be written with write().
            format: An optional cell Format object.
        Returns:
            0:  Success.
            other: Return value of write() method.

        """
        for token in (data):
            error = self.write(row, col, token, cell_format)
            if error:
                return error
            col += 1

        return 0

    @convert_cell_args
    def write_column(self, row, col, data, cell_format=None):
        """
        Write a column of data starting from (row, col).

        Args:
            row:    The cell row (zero indexed).
            col:    The cell column (zero indexed).
            data:   A list of tokens to be written with write().
            format: An optional cell Format object.
        Returns:
            0:  Success.
            other: Return value of write() method.

        """
        for token in (data):
            error = self.write(row, col, token, cell_format)
            if error:
                return error
            row += 1

        return 0

    @convert_cell_args
    def insert_image(self, row, col, image, options={}):
        """
        Insert an image with its top-left corner in a worksheet cell.
        Args:
            row:     The cell row (zero indexed).
            col:     The cell column (zero indexed).
            image:   Path and filename for image in PNG, JPG or BMP format.
            options: Position and scale of the image..

        Returns:
            0:  Success.
        """
        x_offset = options.get('x_offset', 0)
        y_offset = options.get('y_offset', 0)
        x_scale = options.get('x_scale', 1)
        y_scale = options.get('y_scale', 1)

        # if not -e image:
        #    croak "Couldn't locate image: $!"

        self.images.append([row, col, image, x_offset, y_offset,
                            x_scale, y_scale])

    @convert_cell_args
    def write_comment(self, row, col, comment, options={}):
        """
        Write a comment to a worksheet cell.

        Args:
            row:     The cell row (zero indexed).
            col:     The cell column (zero indexed).
            comment: Cell comment. Str.
            options: Comment formatting options.

        Returns:
            0:  Success.
            -1: Row or column is out of worksheet bounds.
            -2: String longer than 32k characters.

        """
        # Check that row and col are valid and store max and min values
        if self._check_dimensions(row, col):
            return -1

        # Check that the comment string is < 32767 chars.
        if len(comment) > self.xls_strmax:
            return -2

        self.has_vml = 1
        self.has_comments = 1

        # Process the properties of the cell comment.
        self.comments[row][col] = \
            self._comment_params(row, col, comment, options)

    def show_comments(self):
        """
        Make any comments in the worksheet visible.

        Args:
            None.

        Returns:
            Nothing.

        """
        self.comments_visible = 1

    def set_comments_author(self, author):
        """
        Set the default author of the cell comments.

        Args:
            author: Comment author name. String.

        Returns:
            Nothing.

        """
        self.comments_author = author

    def get_name(self):
        """
        Retrieve the worksheet name.

        Args:
            None.

        Returns:
            Nothing.

        """
        # There is no set_name() method. Name must be set in add_worksheet().
        return self.name

    def activate(self):
        """
        Set this worksheet as the active worksheet, i.e. the worksheet that is
        displayed when the workbook is opened. Also set it as selected.

        Note: An active worksheet cannot be hidden.

        Args:
            None.

        Returns:
            Nothing.

        """
        self.hidden = 0
        self.selected = 1
        self.worksheet_meta.activesheet = self.index

    def select(self):
        """
        Set current worksheet as a selected worksheet, i.e. the worksheet
        has its tab highlighted.

        Note: A selected worksheet cannot be hidden.

        Args:
            None.

        Returns:
            Nothing.

        """
        self.selected = 1
        self.hidden = 0

    def hide(self):
        """
        Hide the current worksheet.

        Args:
            None.

        Returns:
            Nothing.

        """
        self.hidden = 1

        # A hidden worksheet shouldn't be active or selected.
        self.selected = 0
        self.activesheet = 0
        self.firstsheet = 0

    def set_first_sheet(self):
        """
        Set current worksheet as the first visible sheet. This is necessary
        when there are a large number of worksheets and the activated
        worksheet is not visible on the screen.

        Note: A selected worksheet cannot be hidden.

        Args:
            None.

        Returns:
            Nothing.

        """
        self.hidden = 0  # Active worksheet can't be hidden.
        self.worksheet_meta.firstsheet = self.index

    @convert_column_args
    def set_column(self, firstcol, lastcol, width=None, cell_format=None,
                   options={}):
        """
        Set the width, and other properties of a single column or a
        range of columns.

        Args:
            firstcol:    First column (zero-indexed).
            lastcol:     Last column (zero-indexed). Can be same as firstcol.
            width:       Column width. (optional).
            cell_format: Column cell_format. (optional).
            options:     Dict of options such as hidden and level.

        Returns:
            0:  Success.
            -1: Column number is out of worksheet bounds.

        """
        # Ensure 2nd col is larger than first.
        if firstcol > lastcol:
            (firstcol, lastcol) = (lastcol, firstcol)

        # Don't modify the row dimensions when checking the columns.
        ignore_row = 1

        # Set optional column values.
        hidden = options.get('hidden', False)
        collapsed = options.get('collapsed', False)
        level = options.get('level', 0)
        # Store the column dimension only in some conditions.
        if cell_format or (width and hidden):
            ignore_col = 0
        else:
            ignore_col = 1

        # Check that each column is valid and store the max and min values.
        if self._check_dimensions(0, lastcol, ignore_row, ignore_col):
            return -1
        if self._check_dimensions(0, firstcol, ignore_row, ignore_col):
            return -1

        # Set the limits for the outline levels (0 <= x <= 7).
        if level < 0:
            level = 0
        if level > 7:
            level = 7

        if level > self.outline_col_level:
            self.outline_col_level = level

        # Store the column data.
        self.colinfo.append([firstcol, lastcol, width, cell_format, hidden,
                             level, collapsed])

        # Store the column change to allow optimisations.
        self.col_size_changed = 1

        # Store the col sizes for use when calculating image vertices taking
        # hidden columns into account. Also store the column formats.

        # Set width to zero if col is hidden
        if hidden:
            width = 0

        for col in range(firstcol, lastcol + 1):
            self.col_sizes[col] = width
            if cell_format:
                self.col_formats[col] = cell_format

        return 0

    def set_row(self, row, height=None, cell_format=None, options={}):
        """
        Set the width, and other properties of a row.
        range of columns.

        Args:
            row:         Row number (zero-indexed).
            height:      Row width. (optional).
            cell_format: Row cell_format. (optional).
            options:     Dict of options such as hidden, level and collapsed.

        Returns:
            0:  Success.
            -1: Row number is out of worksheet bounds.

        """
        # Use minimum col in _check_dimensions().
        if self.dim_colmin is not None:
            min_col = self.dim_colmin
        else:
            min_col = 0

        # Check that row is valid.
        if self._check_dimensions(row, min_col):
            return -1

        if height is None:
            height = self.default_row_height

        # Set optional row values.
        hidden = options.get('hidden', False)
        collapsed = options.get('collapsed', False)
        level = options.get('level', 0)

        # If the height is 0 the row is hidden and the height is the default.
        if height == 0:
            hidden = 1
            height = self.default_row_height

        # Set the limits for the outline levels (0 <= x <= 7).
        if level < 0:
            level = 0
        if level > 7:
            level = 7

        if level > self.outline_row_level:
            self.outline_row_level = level

        # Store the row properties.
        self.set_rows[row] = [height, cell_format, hidden, level, collapsed]

        # Store the row change to allow optimisations.
        self.row_size_changed = 1

        # Store the row sizes for use when calculating image vertices.
        self.row_sizes[row] = height

    def set_default_row(self, height=15, hide_unused_rows=False):
        """
        Set the default row properties.

        Args:
            height:           Default height. Optional, defaults to 15.
            hide_unused_rows: Hide unused rows. Optional, defaults to False.

        Returns:
            Nothing.

        """
        if height != 15:
            # Store the row change to allow optimisations.
            self.row_size_changed = 1
            self.default_row_height = height

        if hide_unused_rows:
            self.default_row_zeroed = 1

    @convert_range_args
    def merge_range(self, first_row, first_col, last_row, last_col,
                    data, cell_format=None):
        """
        Merge a range of cells.

        Args:
            first_row:    The first row of the cell range. (zero indexed).
            first_col:    The first column of the cell range.
            last_row:     The last row of the cell range. (zero indexed).
            last_col:     The last column of the cell range.
            data:         Cell data.
            cell_format:  Cell Format object.

        Returns:
             0:    Success.
            -1:    Row or column is out of worksheet bounds.
            other: Return value of write().

        """
        # Merge a range of cells. The first cell should contain the data and
        # the others should be blank. All cells should have the same format.

        # Excel doesn't allow a single cell to be merged
        if first_row == last_row and first_col == last_col:
            warn("Can't merge single cell")
            return

        # Swap last row/col with first row/col as necessary
        if first_row > last_row:
            (first_row, last_row) = (last_row, first_row)
        if first_col > last_col:
            (first_col, last_col) = (last_col, first_col)

        # Check that column number is valid and store the max value
        if self._check_dimensions(last_row, first_col):
            return

        # Store the merge range.
        self.merge.append([first_row, first_col, last_row, last_col])

        # Write the first cell
        self.write(first_row, first_col, data, cell_format)

        # Pad out the rest of the area with formatted blank cells.
        for row in range(first_row, last_row + 1):
            for col in range(first_col, last_col + 1):
                if row == first_row and col == first_col:
                    continue
                self.write_blank(row, col, '', cell_format)

    @convert_range_args
    def autofilter(self, first_row, first_col, last_row, last_col):
        """
        Set the autofilter area in the worksheet.

        Args:
            first_row:    The first row of the cell range. (zero indexed).
            first_col:    The first column of the cell range.
            last_row:     The last row of the cell range. (zero indexed).
            last_col:     The last column of the cell range.

        Returns:
             Nothing.

        """
        # Reverse max and min values if necessary.
        if last_row < first_row:
            (first_row, last_row) = (last_row, first_row)
        if last_col < first_col:
            (first_col, last_col) = (last_col, first_col)

        # Build up the print area range "Sheet1!$A$1:$C$13".
        area = self._convert_name_area(first_row, first_col,
                                       last_row, last_col)
        ref = xl_range(first_row, first_col, last_row, last_col)

        self.autofilter_area = area
        self.autofilter_ref = ref
        self.filter_range = [first_col, last_col]

    def filter_column(self, col, criteria):
        """
        Set the column filter criteria.

        Args:
            col:       Filter column (zero-indexed).
            criteria:  Filter criteria.

        Returns:
             Nothing.

        """
        if not self.autofilter_area:
            warn("Must call autofilter() before filter_column()")
            return

        # Check for a column reference in A1 notation and substitute.
        try:
            int(col)
        except ValueError:
            # Convert col ref to a cell ref and then to a col number.
            col_letter = col
            (_, col) = xl_cell_to_rowcol(col + '1')

            if col >= self.xls_colmax:
                warn("Invalid column '%d'" % col_letter)
                return

        (col_first, col_last) = self.filter_range

        # Reject column if it is outside filter range.
        if col < col_first or col > col_last:
            warn("Column '%d' outside autofilter() column range (%d, %d)"
                 % (col, col_first, col_last))
            return

        tokens = self._extract_filter_tokens(criteria)

        if not (len(tokens) == 3 or len(tokens) == 7):
            warn("Incorrect number of tokens in criteria '%s'" % criteria)

        tokens = self._parse_filter_expression(criteria, tokens)

        # Excel handles single or double custom filters as default filters.
        #  We need to check for them and handle them accordingly.
        if len(tokens) == 2 and tokens[0] == 2:
            # Single equality.
            self.filter_column_list(col, [tokens[1]])
        elif (len(tokens) == 5 and tokens[0] == 2 and tokens[2] == 1
              and tokens[3] == 2):
            # Double equality with "or" operator.
            self.filter_column_list(col, [tokens[1], tokens[4]])
        else:
            # Non default custom filter.
            self.filter_cols[col] = tokens
            self.filter_type[col] = 0

        self.filter_on = 1

    def filter_column_list(self, col, filters):
        """
        Set the column filter criteria in Excel 2007 list style.

        Args:
            col:      Filter column (zero-indexed).
            filters:  List of filter criteria to match.

        Returns:
             Nothing.

        """
        if not self.autofilter_area:
            warn("Must call autofilter() before filter_column()")
            return

        # Check for a column reference in A1 notation and substitute.
        try:
            int(col)
        except ValueError:
            # Convert col ref to a cell ref and then to a col number.
            col_letter = col
            (_, col) = xl_cell_to_rowcol(col + '1')

            if col >= self.xls_colmax:
                warn("Invalid column '%d'" % col_letter)
                return

        (col_first, col_last) = self.filter_range

        # Reject column if it is outside filter range.
        if col < col_first or col > col_last:
            warn("Column '%d' outside autofilter() column range "
                 "(%d,%d)" % (col, col_first, col_last))
            return

        self.filter_cols[col] = filters
        self.filter_type[col] = 1
        self.filter_on = 1

    @convert_range_args
    def data_validation(self, first_row, first_col, last_row, last_col,
                        options):
        """
        Add a data validation to a worksheet.

        Args:
            first_row:    The first row of the cell range. (zero indexed).
            first_col:    The first column of the cell range.
            last_row:     The last row of the cell range. (zero indexed).
            last_col:     The last column of the cell range.
            options:      Data validation options.

        Returns:
            0:  Success.
            -1: Row or column is out of worksheet bounds.
            -2: incorrect parameter or option.
        """
        # Check that row and col are valid without storing the values.
        if self._check_dimensions(first_row, first_col, 1, 1):
            return -1
        if self._check_dimensions(last_row, last_col, 1, 1):
            return -1

        # List of valid input parameters.
        valid_parameters = {
            'validate': 1,
            'criteria': 1,
            'value': 1,
            'source': 1,
            'minimum': 1,
            'maximum': 1,
            'ignore_blank': 1,
            'dropdown': 1,
            'show_input': 1,
            'input_title': 1,
            'input_message': 1,
            'show_error': 1,
            'error_title': 1,
            'error_message': 1,
            'error_type': 1,
            'other_cells': 1,
        }

        # Check for valid input parameters.
        for param_key in options.keys():
            if not param_key in valid_parameters:
                warn("Unknown parameter 'param_key' in data_validation()")
                return -2

        # Map alternative parameter names 'source' or 'minimum' to 'value'.
        if 'source' in options:
            options['value'] = options['source']
        if 'minimum' in options:
            options['value'] = options['minimum']

        # 'validate' is a required parameter.
        if not 'validate' in options:
            warn("Parameter 'validate' is required in data_validation()")
            return -2

        # List of  valid validation types.
        valid_types = {
            'any': 'none',
            'any value': 'none',
            'whole number': 'whole',
            'whole': 'whole',
            'integer': 'whole',
            'decimal': 'decimal',
            'list': 'list',
            'date': 'date',
            'time': 'time',
            'text length': 'textLength',
            'length': 'textLength',
            'custom': 'custom',
        }

        # Check for valid validation types.
        if not options['validate'] in valid_types:
            warn("Unknown validation type '%s' for parameter "
                 "'validate' in data_validation()" % options['validate'])
            return -2
        else:
            options['validate'] = valid_types[options['validate']]

        # No action is required for validation type 'any'.
        if options['validate'] == 'none':
            return -2

        # The list and custom validations don't have a criteria so we use
        # a default of 'between'.
        if options['validate'] == 'list' or options['validate'] == 'custom':
            options['criteria'] = 'between'
            options['maximum'] = None

        # 'criteria' is a required parameter.
        if not 'criteria' in options:
            warn("Parameter 'criteria' is required in data_validation()")
            return -2

        # List of valid criteria types.
        criteria_types = {
            'between': 'between',
            'not between': 'notBetween',
            'equal to': 'equal',
            '=': 'equal',
            '==': 'equal',
            'not equal to': 'notEqual',
            '!=': 'notEqual',
            '<>': 'notEqual',
            'greater than': 'greaterThan',
            '>': 'greaterThan',
            'less than': 'lessThan',
            '<': 'lessThan',
            'greater than or equal to': 'greaterThanOrEqual',
            '>=': 'greaterThanOrEqual',
            'less than or equal to': 'lessThanOrEqual',
            '<=': 'lessThanOrEqual',
        }

        # Check for valid criteria types.
        if not options['criteria'] in criteria_types:
            warn("Unknown criteria type '%s' for parameter "
                 "'criteria' in data_validation()" % options['criteria'])
            return -2
        else:
            options['criteria'] = criteria_types[options['criteria']]

        # 'Between' and 'Not between' criteria require 2 values.
        if (options['criteria'] == 'between' or
                options['criteria'] == 'notBetween'):
            if not 'maximum' in options:
                warn("Parameter 'maximum' is required in data_validation() "
                     "when using 'between' or 'not between' criteria")
                return -2
        else:
            options['maximum'] = None

        # List of valid error dialog types.
        error_types = {
            'stop': 0,
            'warning': 1,
            'information': 2,
        }

        # Check for valid error dialog types.
        if not 'error_type' in options:
            options['error_type'] = 0
        elif not options['error_type'] in error_types:
            warn("Unknown criteria type '%s' for parameter 'error_type' "
                 "in data_validation()" % options['error_type'])
            return -2
        else:
            options['error_type'] = error_types[options['error_type']]

        # Convert date/times value if required.
        if options['validate'] == 'date' or options['validate'] == 'time':

            if options['value']:
                if not self._is_supported_datetime(options['value']):
                    warn("Data validation 'value/minimum' must be a "
                         "datetime object.")
                    return -2
                else:
                    date_time = self._convert_date_time(options['value'])
                    # Format date number to the same precision as Excel.
                    options['value'] = "%.15g" % date_time

            if options['maximum']:
                if not self._is_supported_datetime(options['maximum']):
                    warn("Conditional format 'maximum' must be a "
                         "datetime object.")
                    return -2
                else:
                    date_time = self._convert_date_time(options['maximum'])
                    options['maximum'] = "%.15g" % date_time

        # Set some defaults if they haven't been defined by the user.
        if not 'ignore_blank' in options:
            options['ignore_blank'] = 1
        if not 'dropdown' in options:
            options['dropdown'] = 1
        if not 'show_input' in options:
            options['show_input'] = 1
        if not 'show_error' in options:
            options['show_error'] = 1

        # These are the cells to which the validation is applied.
        options['cells'] = [[first_row, first_col, last_row, last_col]]

        # A (for now) undocumented parameter to pass additional cell ranges.
        if 'other_cells' in options:
            options['cells'].extend(options['other_cells'])

        # Store the validation information until we close the worksheet.
        self.validations.append(options)

    @convert_range_args
    def conditional_format(self, first_row, first_col, last_row, last_col,
                           options=None):
        """
        Add a conditional format to a worksheet.

        Args:
            first_row:    The first row of the cell range. (zero indexed).
            first_col:    The first column of the cell range.
            last_row:     The last row of the cell range. (zero indexed).
            last_col:     The last column of the cell range.
            options:      Conditional format options.

        Returns:
            0:  Success.
            -1: Row or column is out of worksheet bounds.
            -2: incorrect parameter or option.
        """
        # Check that row and col are valid without storing the values.
        if self._check_dimensions(first_row, first_col, 1, 1):
            return -1
        if self._check_dimensions(last_row, last_col, 1, 1):
            return -1

        if options is None:
            options = {}

        # List of valid input parameters.
        valid_parameter = {
            'type': 1,
            'format': 1,
            'criteria': 1,
            'value': 1,
            'minimum': 1,
            'maximum': 1,
            'min_type': 1,
            'mid_type': 1,
            'max_type': 1,
            'min_value': 1,
            'mid_value': 1,
            'max_value': 1,
            'min_color': 1,
            'mid_color': 1,
            'max_color': 1,
            'multi_range': 1,
            'bar_color': 1}

        # Check for valid input parameters.
        for param_key in options.keys():
            if param_key not in valid_parameter:
                warn("Unknown parameter '%s' in conditional_formatting()" %
                     param_key)
                return -2

        # 'type' is a required parameter.
        if 'type' not in options:
            warn("Parameter 'type' is required in conditional_formatting()")
            return -2

        # List of  valid validation types.
        valid_type = {
            'cell': 'cellIs',
            'date': 'date',
            'time': 'time',
            'average': 'aboveAverage',
            'duplicate': 'duplicateValues',
            'unique': 'uniqueValues',
            'top': 'top10',
            'bottom': 'top10',
            'text': 'text',
            'time_period': 'timePeriod',
            'blanks': 'containsBlanks',
            'no_blanks': 'notContainsBlanks',
            'errors': 'containsErrors',
            'no_errors': 'notContainsErrors',
            '2_color_scale': '2_color_scale',
            '3_color_scale': '3_color_scale',
            'data_bar': 'dataBar',
            'formula': 'expression'}

        # Check for valid validation types.
        if options['type'] not in valid_type:
            warn("Unknown validation type '%s' for parameter 'type' "
                 "in conditional_formatting()" % options['type'])
            return -2
        else:
            if options['type'] == 'bottom':
                options['direction'] = 'bottom'
            options['type'] = valid_type[options['type']]

        # List of valid criteria types.
        criteria_type = {
            'between': 'between',
            'not between': 'notBetween',
            'equal to': 'equal',
            '=': 'equal',
            '==': 'equal',
            'not equal to': 'notEqual',
            '!=': 'notEqual',
            '<>': 'notEqual',
            'greater than': 'greaterThan',
            '>': 'greaterThan',
            'less than': 'lessThan',
            '<': 'lessThan',
            'greater than or equal to': 'greaterThanOrEqual',
            '>=': 'greaterThanOrEqual',
            'less than or equal to': 'lessThanOrEqual',
            '<=': 'lessThanOrEqual',
            'containing': 'containsText',
            'not containing': 'notContains',
            'begins with': 'beginsWith',
            'ends with': 'endsWith',
            'yesterday': 'yesterday',
            'today': 'today',
            'last 7 days': 'last7Days',
            'last week': 'lastWeek',
            'this week': 'thisWeek',
            'continue week': 'continueWeek',
            'last month': 'lastMonth',
            'this month': 'thisMonth',
            'continue month': 'continueMonth'}

        # Check for valid criteria types.
        if ('criteria' in options and options['criteria'] in criteria_type):
            options['criteria'] = criteria_type[options['criteria']]

        # Convert date/times value if required.
        if options['type'] == 'date' or options['type'] == 'time':
            options['type'] = 'cellIs'

            if 'value' in options:
                if not self._is_supported_datetime(options['value']):
                    warn("Conditional format 'value' must be a "
                         "datetime object.")
                    return -2
                else:
                    date_time = self._convert_date_time(options['value'])
                    # Format date number to the same precision as Excel.
                    options['value'] = "%.15g" % date_time

            if 'minimum' in options:
                if not self._is_supported_datetime(options['minimum']):
                    warn("Conditional format 'minimum' must be a "
                         "datetime object.")
                    return -2
                else:
                    date_time = self._convert_date_time(options['minimum'])
                    options['minimum'] = "%.15g" % date_time

            if 'maximum' in options:
                if not self._is_supported_datetime(options['maximum']):
                    warn("Conditional format 'maximum' must be a "
                         "datetime object.")
                    return -2
                else:
                    date_time = self._convert_date_time(options['maximum'])
                    options['maximum'] = "%.15g" % date_time

        # Swap last row/col for first row/col as necessary
        if first_row > last_row:
            first_row, last_row = last_row, first_row

        if first_col > last_col:
            first_col, last_col = last_col, first_col

        # Set the formatting range.
        # If the first and last cell are the same write a single cell.
        if first_row == last_row and first_col == last_col:
            cell_range = xl_rowcol_to_cell(first_row, first_col)
            start_cell = cell_range
        else:
            cell_range = xl_range(first_row, first_col, last_row, last_col)
            start_cell = xl_rowcol_to_cell(first_row, first_col)

        # Override with user defined multiple range if provided.
        if 'multi_range' in options:
            cell_range = options['multi_range']
            cell_range = cell_range.replace('$', '')

        # Get the dxf format index.
        if 'format' in options and options['format']:
            options['format'] = options['format']._get_dxf_index()

        # Set the priority based on the order of adding.
        options['priority'] = self.dxf_priority
        self.dxf_priority += 1

        # Special handling of text criteria.
        if options['type'] == 'text':

            if options['criteria'] == 'containsText':
                options['type'] = 'containsText'
                options['formula'] = ('NOT(ISERROR(SEARCH("%s",%s)))'
                                      % (options['value'], start_cell))
            elif options['criteria'] == 'notContains':
                options['type'] = 'notContainsText'
                options['formula'] = ('ISERROR(SEARCH("%s",%s))'
                                      % (options['value'], start_cell))
            elif options['criteria'] == 'beginsWith':
                options['type'] = 'beginsWith'
                options['formula'] = ('LEFT(%s,%d)="%s"'
                                      % (start_cell,
                                         len(options['value']),
                                         options['value']))
            elif options['criteria'] == 'endsWith':
                options['type'] = 'endsWith'
                options['formula'] = ('RIGHT(%s,%d)="%s"'
                                      % (start_cell,
                                         len(options['value']),
                                         options['value']))
            else:
                warn("Invalid text criteria 'options['criteria']' "
                     "in conditional_formatting()")

        # Special handling of time time_period criteria.
        if options['type'] == 'timePeriod':

            if options['criteria'] == 'yesterday':
                options['formula'] = 'FLOOR(%s,1)=TODAY()-1' % start_cell

            elif options['criteria'] == 'today':
                options['formula'] = 'FLOOR(%s,1)=TODAY()' % start_cell

            elif options['criteria'] == 'tomorrow':
                options['formula'] = 'FLOOR(%s,1)=TODAY()+1' % start_cell

            elif options['criteria'] == 'last7Days':
                options['formula'] = \
                    ('AND(TODAY()-FLOOR(%s,1)<=6,FLOOR(%s,1)<=TODAY())' %
                    (start_cell, start_cell))

            elif options['criteria'] == 'lastWeek':
                options['formula'] = \
                    ('AND(TODAY()-ROUNDDOWN(%s,0)>=(WEEKDAY(TODAY())),'
                     'TODAY()-ROUNDDOWN(%s,0)<(WEEKDAY(TODAY())+7))' %
                     (start_cell, start_cell))

            elif options['criteria'] == 'thisWeek':
                options['formula'] = \
                    ('AND(TODAY()-ROUNDDOWN(%s,0)<=WEEKDAY(TODAY())-1,'
                     'ROUNDDOWN(%s,0)-TODAY()<=7-WEEKDAY(TODAY()))' %
                     (start_cell, start_cell))

            elif options['criteria'] == 'continueWeek':
                options['formula'] = \
                    ('AND(ROUNDDOWN(%s,0)-TODAY()>(7-WEEKDAY(TODAY())),'
                     'ROUNDDOWN(%s,0)-TODAY()<(15-WEEKDAY(TODAY())))' %
                     (start_cell, start_cell))

            elif options['criteria'] == 'lastMonth':
                options['formula'] = \
                    ('AND(MONTH(%s)=MONTH(TODAY())-1,OR(YEAR(%s)=YEAR('
                     'TODAY()),AND(MONTH(%s)=1,YEAR(A1)=YEAR(TODAY())-1)))' %
                     (start_cell, start_cell, start_cell))

            elif options['criteria'] == 'thisMonth':
                options['formula'] = \
                    ('AND(MONTH(%s)=MONTH(TODAY()),YEAR(%s)=YEAR(TODAY()))' %
                    (start_cell, start_cell))

            elif options['criteria'] == 'continueMonth':
                options['formula'] = \
                    ('AND(MONTH(%s)=MONTH(TODAY())+1,OR(YEAR(%s)=YEAR('
                     'TODAY()),AND(MONTH(%s)=12,YEAR(%s)=YEAR(TODAY())+1)))' %
                     (start_cell, start_cell, start_cell, start_cell))

            else:
                warn("Invalid time_period criteria 'options['criteria']' "
                     "in conditional_formatting()")

        # Special handling of blanks/error types.
        if options['type'] == 'containsBlanks':
            options['formula'] = 'LEN(TRIM(%s))=0' % start_cell

        if options['type'] == 'notContainsBlanks':
            options['formula'] = 'LEN(TRIM(%s))>0' % start_cell

        if options['type'] == 'containsErrors':
            options['formula'] = 'ISERROR(%s)' % start_cell

        if options['type'] == 'notContainsErrors':
            options['formula'] = 'NOT(ISERROR(%s))' % start_cell

        # Special handling for 2 color scale.
        if options['type'] == '2_color_scale':
            options['type'] = 'colorScale'

            # Color scales don't use any additional formatting.
            options['format'] = None

            # Turn off 3 color parameters.
            options['mid_type'] = None
            options['mid_color'] = None

            options.setdefault('min_type', 'min')
            options.setdefault('max_type', 'max')
            options.setdefault('min_value', 0)
            options.setdefault('max_value', 0)
            options.setdefault('min_color', '#FF7128')
            options.setdefault('max_color', '#FFEF9C')

            options['min_color'] = xl_color(options['min_color'])
            options['max_color'] = xl_color(options['max_color'])

        # Special handling for 3 color scale.
        if options['type'] == '3_color_scale':
            options['type'] = 'colorScale'

            # Color scales don't use any additional formatting.
            options['format'] = None

            options.setdefault('min_type', 'min')
            options.setdefault('mid_type', 'percentile')
            options.setdefault('max_type', 'max')
            options.setdefault('min_value', 0)
            options.setdefault('max_value', 0)
            options.setdefault('min_color', '#F8696B')
            options.setdefault('mid_color', '#FFEB84')
            options.setdefault('max_color', '#63BE7B')

            options['min_color'] = xl_color(options['min_color'])
            options['mid_color'] = xl_color(options['mid_color'])
            options['max_color'] = xl_color(options['max_color'])

            # Set a default mid value.
            if not 'mid_value' in options:
                options['mid_value'] = 50

        # Special handling for data bar.
        if options['type'] == 'dataBar':

            # Color scales don't use any additional formatting.
            options['format'] = None

            options.setdefault('min_type', 'min')
            options.setdefault('max_type', 'max')
            options.setdefault('min_value', 0)
            options.setdefault('max_value', 0)
            options.setdefault('bar_color', '#638EC6')

            options['bar_color'] = xl_color(options['bar_color'])

        # Store the validation information until we close the worksheet.
        if cell_range in self.cond_formats:
            self.cond_formats[cell_range].append(options)
        else:
            self.cond_formats[cell_range] = [options]

    #
    #
    # Add an Excel table to a worksheet.
    #
    @convert_range_args
    def add_table(self, row1, col1, row2, col2, param={}):
        """
        TODO.
        """
        table = {}
        col_formats = {}

        if self.optimization == 1:
            warn("add_table() isn't supported when set_optimization() is on")
            return -1

        # Check that row and col are valid without storing the values.
        if self._check_dimensions(row1, col1, 1, 1):
            return -2
        if self._check_dimensions(row2, col2, 1, 1):
            return -2

        # List of valid input parameters.
        valid_parameter = {
            'autofilter': 1,
            'banded_columns': 1,
            'banded_rows': 1,
            'columns': 1,
            'data': 1,
            'first_column': 1,
            'header_row': 1,
            'last_column': 1,
            'name': 1,
            'style': 1,
            'total_row': 1,
        }

        # Check for valid input parameters.
        for param_key in param.keys():
            if not param_key in valid_parameter:
                warn("Unknown parameter '%s' in add_table()" % param_key)
                return -3

        # Table count is a member of Workbook, global to all Worksheet.
        self.worksheet_meta.table_count += 1
        table['id'] = self.worksheet_meta.table_count

        # Turn on Excel's defaults.
        param['banded_rows'] = param.get('banded_rows', 1)
        param['header_row'] = param.get('header_row', 1)
        param['autofilter'] = param.get('autofilter', 1)

        # Set the table options.
        table['show_first_col'] = param.get('first_column', 0)
        table['show_last_col'] = param.get('last_column', 0)
        table['show_row_stripes'] = param.get('banded_rows', 0)
        table['show_col_stripes'] = param.get('banded_columns', 0)
        table['header_row_count'] = param.get('header_row', 0)
        table['totals_row_shown'] = param.get('total_row', 0)

        # Set the table name.
        if 'name' in param:
            table['name'] = param['name']
        else:
            # Set a default name.
            table['name'] = 'Table' + table['id']

        # Set the table style.
        if 'style' in param:
            table['style'] = param['style']
            # Remove whitespace from style name.
            table['style'] = table['style'].replace(' ', '')
        else:
            table['style'] = "TableStyleMedium9"

        # Swap last row/col for first row/col as necessary.
        if row1 > row2:
            (row1, row2) = (row2, row1)
        if col1 > col2:
            (col1, col2) = (col2, col1)

        # Set the data range rows (without the header and footer).
        first_data_row = row1
        last_data_row = row2
        if param['header_row']:
            first_data_row += 1
        if param['total_row']:
            last_data_row -= 1

        # Set the table and autofilter ranges.
        table['range'] = xl_range(row1, row2, col1, col2)
        table['a_range'] = xl_range(row1, col1, last_data_row, col2)

        # If the header row if off the default is to turn autofilter off.
        if not param['header_row']:
            param['autofilter'] = 0

        # Set the autofilter range.
        if param['autofilter']:
            table['autofilter'] = table['a_range']

        # Add the table columns.
        col_id = 1
        for col_num in range(col1, col2 + 1):
            # Set up the default column data.
            col_data = {
                'id': col_id,
                'name': 'Column' + col_id,
                'total_string': '',
                'total_function': '',
                'formula': '',
                'format': None,
            }

            # Overwrite the defaults with any use defined values.
            if param['columns']:
                # Check if there are user defined values for this column.
                user_data = param['columns'][col_id - 1]

                if user_data:
                    # Map user defined values to internal values.
                    if user_data['header']:
                        col_data.name = user_data['header']

                    # Handle the column formula.
                    if user_data['formula']:
                        formula = user_data['formula']

                        # Remove the formula '=' sign if it exists.
                        if formula.startswith('='):
                            formula = formula.lstrip('=')

                        # Covert Excel 2010 "@" ref to 2007 "#This Row".
                        # formula =~ s/@/[#This Row],/g
                        # TODO

                        col_data['formula'] = formula

                        for row in range(first_data_row, last_data_row + 1):
                            self.write_formula(row, col_num, formula,
                                               user_data['format'])

                    # Handle the function for the total row.
                    if user_data['total_function']:
                        function = user_data['total_function']

                        # Massage the function name.
                        # function = lc function
                        # function =~ s/_//g
                        # function =~ s/\s//g

                        if function == 'countnums':
                            function = 'countNums'
                        if function == 'stddev':
                            function = 'stdDev'

                        col_data['total_function'] = function

                        formula = self._table_function_to_formula(
                                                                  function,
                                                                  col_data['name'])

                        self.write_formula(row2, col_num, formula,
                                           user_data['format'])

                    elif user_data['total_string']:
                        # Total label only (not a function).
                        total_string = user_data['total_string']
                        col_data['total_string'] = total_string

                        self.write_string(row2, col_num, total_string,
                                          user_data['format'])

                    # Get the dxf format index.
                    if format in user_data and user_data['format'] is not None:
                        col_data.format = user_data['format'].get_dxf_index()

                    # Store the column format for writing the cell data.
                    # It doesn't matter if it is undefined.
                    col_formats[col_id - 1] = user_data['format']

            # Store the column data.
            table['columns'].append(col_data)

            # Write the column headers to the worksheet.
            if param['header_row']:
                self.write_string(row1, col_num, col_data.name)

            col_id += 1

        # Write the cell data if supplied.
        if 'data' in param['data']:
            data = param['data']

            i = 0  # For indexing the row data.
            for row in range(first_data_row, last_data_row + 1):
                j = 0  # For indexing the col data.
                for col in range(col1, col2 + 1):
                    token = data[i][j]
                    if token:
                        self.write(row, col, token, col_formats[j])
                    j += 1
                i += 1

        # Store the table data.
        self.tables.append(table)

        # Store the link used for the rels file.
        self.external_table_links.append(
          ['/table', '../tables/table' + table['id'] + '.xml'])

        return table

    @convert_range_args
    def set_selection(self, first_row, first_col, last_row, last_col):
        """
        Set the selected cell or cells in a worksheet

        Args:
            first_row:    The first row of the cell range. (zero indexed).
            first_col:    The first column of the cell range.
            last_row:     The last row of the cell range. (zero indexed).
            last_col:     The last column of the cell range.

        Returns:
            0:  Nothing.
        """
        pane = None

        # Range selection. Do this before swapping max/min to allow the
        # selection direction to be reversed.
        active_cell = xl_rowcol_to_cell(first_row, first_col)

        # Swap last row/col for first row/col if necessary
        if first_row > last_row:
            (first_row, last_row) = (last_row, first_row)

        if first_col > last_col:
            (first_col, last_col) = (last_col, first_col)

        # If the first and last cell are the same write a single cell.
        if (first_row == last_row) and (first_col == last_col):
            sqref = active_cell
        else:
            sqref = xl_range(first_row, first_col, last_row, last_col)

        # Selection isn't set for cell A1.
        if sqref == 'A1':
            return

        self.selections = [[pane, active_cell, sqref]]

    # This method sets the properties for outlining and grouping. The defaults
    # correspond to Excel's defaults.
    #
    def outline_settings(self, outline_on=1, outline_below=1, outline_right=1,
                         outline_style=0):
        self.outline_on = outline_on
        self.outline_below = outline_below
        self.outline_right = outline_right
        self.outline_style = outline_style

        self.outline_changed = 1

    @convert_cell_args
    def freeze_panes(self, row, col, top_row=None, left_col=None, pane_type=0):
        """
        Create worksheet panes and mark them as frozen.

        Args:
            row:      The cell row (zero indexed).
            col:      The cell column (zero indexed).
            top_row:  Topmost visible row in scrolling region of pane.
            left_col: Leftmost visible row in scrolling region of pane.

        Returns:
            0:  Nothing.

        """
        if top_row is None:
            top_row = row

        if left_col is None:
            left_col = col

        self.panes = [row, col, top_row, left_col, pane_type]

    @convert_cell_args
    def split_panes(self, x, y, top_row=None, left_col=None):
        """
        Create worksheet panes and mark them as split.

        Args:
            x:        The position for the vertical split.
            y:        The position for the horizontal split.
            top_row:  Topmost visible row in scrolling region of pane.
            left_col: Leftmost visible row in scrolling region of pane.

        Returns:
            0:  Nothing.

        """
        # Same as freeze panes with a different pane type.
        self.freeze_panes(x, y, top_row, left_col, 2)

    def set_zoom(self, zoom=100):
        """
        Set the worksheet zoom factor.

        Args:
            zoom: Scale factor: 10 <= zoom <= 400.

        Returns:
            Nothing.

        """
        # Ensure the zoom scale is in Excel's range.
        if zoom < 10 or zoom > 400:
            warn("Zoom factor %d outside range: 10 <= zoom <= 400" % zoom)
            zoom = 100

        self.zoom = int(zoom)

    def right_to_left(self):
        """
        Display the worksheet right to left for some versions of Excel.

        Args:
            None.

        Returns:
            Nothing.

        """
        self.is_right_to_left = 1

    def hide_zero(self):
        """
        Hide zero values in worksheet cells.

        Args:
            None.

        Returns:
            Nothing.

        """
        self.show_zeros = 0

    def set_tab_color(self, color):
        """
        Set the colour of the worksheet tab.

        Args:
            color: A #RGB color index.

        Returns:
            Nothing.

        """
        self.tab_color = xl_color(color)

    def protect(self, password='', options=None):
        """
        Set the colour of the worksheet tab.

        Args:
            password: An optional password string.
            options:  A dictionary of worksheet objects to protect.

        Returns:
            Nothing.

        """
        if password != '':
            password = self._encode_password(password)

        if not options:
            options = {}

        # Default values for objects that can be protected.
        defaults = {
            'sheet': 1,
            'content': 0,
            'objects': 0,
            'scenarios': 0,
            'format_cells': 0,
            'format_columns': 0,
            'format_rows': 0,
            'insert_columns': 0,
            'insert_rows': 0,
            'insert_hyperlinks': 0,
            'delete_columns': 0,
            'delete_rows': 0,
            'select_locked_cells': 1,
            'sort': 0,
            'autofilter': 0,
            'pivot_tables': 0,
            'select_unlocked_cells': 1}

        # Overwrite the defaults with user specified values.
        for key in (options.keys()):

            if key in defaults:
                defaults[key] = options[key]
            else:
                warn("Unknown protection object: '%s'\n" % key)

        # Set the password after the user defined values.
        defaults['password'] = password

        self.protect_options = defaults

    ###########################################################################
    #
    # Public API. Page Setup methods.
    #
    ###########################################################################
    def set_landscape(self):
        """
        Set the page orientation as landscape.

        Args:
            None.

        Returns:
            Nothing.

        """
        self.orientation = 0
        self.page_setup_changed = 1

    def set_portrait(self):
        """
        Set the page orientation as portrait.

        Args:
            None.

        Returns:
            Nothing.

        """
        self.orientation = 1
        self.page_setup_changed = 1

    def set_page_view(self):
        """
        Set the page view mode.

        Args:
            None.

        Returns:
            Nothing.

        """
        self.page_view = 1

    def set_paper(self, paper_size):
        """
        Set the paper type. US Letter = 1, A4 = 9.

        Args:
            paper_size: Paper index.

        Returns:
            Nothing.

        """
        if paper_size:
            self.paper_size = paper_size
            self.page_setup_changed = 1

    def center_horizontally(self):
        """
        Center the page horizontally.

        Args:
            None.

        Returns:
            Nothing.

        """
        self.print_options_changed = 1
        self.hcenter = 1

    def center_vertically(self):
        """
        Center the page vertically.

        Args:
            None.

        Returns:
            Nothing.

        """
        self.print_options_changed = 1
        self.vcenter = 1

    def set_margins(self, left=0.7, right=0.7, top=0.75, bottom=0.75):
        """
        Set all the page margins in inches.

        Args:
            left:   Left margin.
            right:  Right margin.
            top:    Top margin.
            bottom: Bottom margin.

        Returns:
            Nothing.

        """
        self.margin_left = left
        self.margin_right = right
        self.margin_top = top
        self.margin_bottom = bottom

    def set_header(self, header='', margin=0.3):
        """
        Set the page header caption and optional margin.

        Args:
            header: Header string.
            margin: Header margin.

        Returns:
            Nothing.

        """
        if len(header) >= 255:
            warn('Header string must be less than 255 characters')
            return

        self.header = header
        self.margin_header = margin
        self.header_footer_changed = 1

    def set_footer(self, footer='', margin=0.3):
        """
        Set the page footer caption and optional margin.

        Args:
            footer: Footer string.
            margin: Footer margin.

        Returns:
            Nothing.

        """
        if len(footer) >= 255:
            warn('Footer string must be less than 255 characters')
            return

        self.footer = footer
        self.margin_footer = margin
        self.header_footer_changed = 1

    def repeat_rows(self, first_row, last_row=None):
        """
        Set the rows to repeat at the top of each printed page.

        Args:
            first_row: Start row for range.
            last_row: End row for range.

        Returns:
            Nothing.

        """
        if last_row is None:
            last_row = first_row

        # Convert rows to 1 based.
        first_row += 1
        last_row += 1

        # Create the row range area like: $1:$2.
        area = '$%d:$%d' % (first_row, last_row)

        # Build up the print titles area "Sheet1!$1:$2"
        sheetname = self._quote_sheetname(self.name)
        self.repeat_row_range = sheetname + '!' + area

    @convert_column_args
    def repeat_columns(self, first_col, last_col=None):
        """
        Set the columns to repeat at the left hand side of each printed page.

        Args:
            first_col: Start column for range.
            last_col: End column for range.

        Returns:
            Nothing.

        """
        if last_col is None:
            last_col = first_col

        # Convert to A notation.
        first_col = xl_col_to_name(first_col, 1)
        last_col = xl_col_to_name(last_col, 1)

        # Create a column range like $C:$D.
        area = first_col + ':' + last_col

        # Build up the print area range "=Sheet2!$C:$D"
        sheetname = self._quote_sheetname(self.name)
        self.repeat_col_range = sheetname + "!" + area

    def hide_gridlines(self, option=1):
        """
        Set the option to hide gridlines on the screen and the printed page.

        Args:
            option:    0 : Don't hide gridlines
                       1 : Hide printed gridlines only
                       2 : Hide screen and printed gridlines

        Returns:
            Nothing.

        """
        if option == 0:
            self.print_gridlines = 1
            self.screen_gridlines = 1
            self.print_options_changed = 1
        elif option == 1:
            self.print_gridlines = 0
            self.screen_gridlines = 1
        else:
            self.print_gridlines = 0
            self.screen_gridlines = 0

    def print_row_col_headers(self):
        """
        Set the option to print the row and column headers on the printed page.

        Args:
            None.

        Returns:
            Nothing.

        """
        self.print_headers = 1
        self.print_options_changed = 1

    @convert_range_args
    def print_area(self, first_row, first_col, last_row, last_col):
        """
        Set the print area in the current worksheet.

        Args:
            first_row:    The first row of the cell range. (zero indexed).
            first_col:    The first column of the cell range.
            last_row:     The last row of the cell range. (zero indexed).
            last_col:     The last column of the cell range.

        Returns:
            0:  Success.
            -1: Row or column is out of worksheet bounds.

        """
        # Set the print area in the current worksheet.

        # Ignore max print area since it is the same as no  area for Excel.
        if (first_row == 0 and first_col == 0
                and last_row == self.xls_rowmax - 1
                and last_col == self.xls_colmax - 1):
            return

        # Build up the print area range "Sheet1!$A$1:$C$13".
        area = self._convert_name_area(first_row, first_col,
                                       last_row, last_col)
        self.print_area_range = area

    def print_across(self):
        """
        Set the order in which pages are printed.

        Args:
            None.

        Returns:
            Nothing.

        """
        self.page_order = 1
        self.page_setup_changed = 1

    def fit_to_pages(self, width, height):
        """
        Fit the printed area to a specific number of pages both vertically and
        horizontally.

        Args:
            width:  Number of pages horizontally.
            height: Number of pages vertically.

        Returns:
            Nothing.

        """
        self.fit_page = 1
        self.fit_width = width
        self.fit_height = height
        self.page_setup_changed = 1

    def set_start_page(self, start_page):
        """
        Set the start page number when printing.

        Args:
            start_page: Start page number.

        Returns:
            Nothing.

        """
        self.page_start = start_page
        self.custom_start = 1

    def set_print_scale(self, scale):
        """
        Set the scale factor for the printed page.

        Args:
            scale: Print scale. 10 <= scale <= 400.

        Returns:
            Nothing.

        """
        # Confine the scale to Excel's range.
        if scale < 10 or scale > 400:
            warn("Print scale '%d' outside range: 10 <= scale <= 400" % scale)
            return

        # Turn off "fit to page" option when print scale is on.
        self.fit_page = 0

        self.print_scale = int(scale)
        self.page_setup_changed = 1

    def set_h_pagebreaks(self, breaks):
        """
        Set the horizontal page breaks on a worksheet.

        Args:
            breaks: List of rows where the page breaks should be added.

        Returns:
            Nothing.

        """
        self.hbreaks = breaks

    #
    # set_v_pagebreaks(@breaks)
    #
    # Store the vertical page breaks on a worksheet.
    #
    def set_v_pagebreaks(self, breaks):
        """
        Set the horizontal page breaks on a worksheet.

        Args:
            breaks: List of columns where the page breaks should be added.

        Returns:
            Nothing.

        """
        self.vbreaks = breaks

    ###########################################################################
    #
    # Private API.
    #
    ###########################################################################
    def _initialize(self, init_data):
        self.name = init_data['name']
        self.index = init_data['index']
        self.str_table = init_data['str_table']
        self.worksheet_meta = init_data['worksheet_meta']
        self.optimization = init_data['optimization']
        self.tmpdir = init_data['tmpdir']
        self.date_1904 = init_data['date_1904']

        if self.date_1904:
            self.epoch = datetime.datetime(1904, 1, 1)

        # Open a temp filehandle to store row data in optimization mode.
        if self.optimization == 1:
            # This make be sub-optimal or insecure. It seems like too much
            # work to create a temp file with utf8 encoding in Python < 3.
            (fd, filename) = tempfile.mkstemp(dir=self.tmpdir)
            os.close(fd)
            self.row_data_filename = filename
            self.row_data_fh = codecs.open(filename, 'w+', 'utf-8')

            # Also use this as the worksheet filehandle until the file is
            # due to be assembled.
            self.fh = self.row_data_fh

    def _assemble_xml_file(self):
        # Assemble and write the XML file.

        # Write the XML declaration.
        self._xml_declaration()

        # Write the root worksheet element.
        self._write_worksheet()

        # Write the worksheet properties.
        self._write_sheet_pr()

        # Write the worksheet dimensions.
        self._write_dimension()

        # Write the sheet view properties.
        self._write_sheet_views()

        # Write the sheet format properties.
        self._write_sheet_format_pr()

        # Write the sheet column info.
        self._write_cols()

        # Write the worksheet data such as rows columns and cells.
        if self.optimization == 0:
            self._write_sheet_data()
        else:
            self._write_optimized_sheet_data()

        # Write the sheetProtection element.
        self._write_sheet_protection()

        # Write the worksheet calculation properties.
        # self._write_sheet_calc_pr()

        # Write the worksheet phonetic properties.
        # self._write_phonetic_pr()

        # Write the autoFilter element.
        self._write_auto_filter()

        # Write the mergeCells element.
        self._write_merge_cells()

        # Write the conditional formats.
        self._write_conditional_formats()

        # Write the dataValidations element.
        self._write_data_validations()

        # Write the hyperlink element.
        self._write_hyperlinks()

        # Write the printOptions element.
        self._write_print_options()

        # Write the worksheet page_margins.
        self._write_page_margins()

        # Write the worksheet page setup.
        self._write_page_setup()

        # Write the headerFooter element.
        self._write_header_footer()

        # Write the rowBreaks element.
        self._write_row_breaks()

        # Write the colBreaks element.
        self._write_col_breaks()

        # Write the drawing element.
        self._write_drawings()

        # Write the legacyDrawing element.
        self._write_legacy_drawing()

        # Write the tableParts element.
        # self._write_table_parts()

        # Write the extLst and sparklines.
        # self._write_ext_sparklines()

        # Close the worksheet tag.
        self._xml_end_tag('worksheet')

        # Close the file.
        self._xml_close()

    def _check_dimensions(self, row, col, ignore_row=False, ignore_col=False):
        # Check that row and col are valid and store the max and min
        # values for use in other methods/elements. The ignore_row /
        # ignore_col flags is used to indicate that we wish to perform
        # the dimension check without storing the value. The ignore
        # flags are use by set_row() and data_validate.

        # Check that the row/col are within the worksheet bounds.
        if row >= self.xls_rowmax or col >= self.xls_colmax:
            return -1

        # In optimization mode we don't change dimensions for rows
        # that are already written.
        if not ignore_row and not ignore_col and self.optimization == 1:
            if row < self.previous_row:
                return -1

        if not ignore_row:
            if self.dim_rowmin is None or row < self.dim_rowmin:
                self.dim_rowmin = row
            if self.dim_rowmax is None or row > self.dim_rowmax:
                self.dim_rowmax = row

        if not ignore_col:
            if self.dim_colmin is None or col < self.dim_colmin:
                self.dim_colmin = col
            if self.dim_colmax is None or col > self.dim_colmax:
                self.dim_colmax = col

        return 0

    def _convert_date_time(self, dt_obj):
        # We handle datetime .datetime, .date and .time objects but convert
        # them to datetime.datetime objects and process them in the same way.
        if isinstance(dt_obj, datetime.datetime):
            pass
        elif isinstance(dt_obj, datetime.date):
            dt_obj = datetime.datetime.fromordinal(dt_obj.toordinal())
        elif isinstance(dt_obj, datetime.time):
            dt_obj = datetime.datetime.combine(self.epoch, dt_obj)
        else:
            raise TypeError("Unknown or unsupported datetime type")

        # Convert a Python datetime.datetime value to an Excel date number.
        delta = dt_obj - self.epoch
        excel_time = (delta.days
                      + (float(delta.seconds)
                      + float(delta.microseconds) / 1E6)
                      / (60 * 60 * 24))

        # Special case for datetime where time only has been specified and
        # the default date of 1900-01-01 is used.
        if dt_obj.isocalendar() == (1900, 1, 1):
            excel_time -= 1

        # Account for Excel erroneously treating 1900 as a leap year.
        if not self.date_1904 and excel_time > 59:
            excel_time += 1

        return excel_time

    def _options_changed(self):
        # Check to see if any of the worksheet options have changed.
        options_changed = 0
        print_changed = 0
        setup_changed = 0

        if (self.orientation == 0
                or self.hcenter == 1
                or self.vcenter == 1
                or self.header != ''
                or self.footer != ''
                or self.margin_header != 0.50
                or self.margin_footer != 0.50
                or self.margin_left != 0.75
                or self.margin_right != 0.75
                or self.margin_top != 1.00
                or self.margin_bottom != 1.00):
            setup_changed = 1

        # Special case for 1x1 page fit.
        if self.fit_width == 1 and self.fit_height == 1:
            options_changed = 1
            self.fit_width = 0
            self.fit_height = 0

        if (self.fit_width > 1
                or self.fit_height > 1
                or self.page_order == 1
                or self.black_white == 1
                or self.draft_quality == 1
                or self.print_comments == 1
                or self.paper_size != 0
                or self.print_scale != 100
                or self.print_gridlines == 1
                or self.print_headers == 1
                or self.hbreaks > 0
                or self.vbreaks > 0):
            print_changed = 1

        if (print_changed or setup_changed):
            options_changed = 1

        if self.screen_gridlines == 0:
            options_changed = 1
        if self.filter_on:
            options_changed = 1

        return (options_changed, print_changed, setup_changed)

    def _quote_sheetname(self, sheetname):
        # Sheetnames used in references should be quoted if they
        # contain any spaces, special characters or if the look like
        # something that isn't a sheet name.
        # TODO. Probably need to handle more special cases.
        if re.match(r'Sheet\d+', sheetname):
            return sheetname
        else:
            return "'%s'" % sheetname

    def _convert_name_area(self, row_num_1, col_num_1, row_num_2, col_num_2):
        # Convert zero indexed rows and columns to the format required by
        # worksheet named ranges, eg, "Sheet1!$A$1:$C$13".

        range1 = ''
        range2 = ''
        area = ''
        row_col_only = 0

        # Convert to A1 notation.
        col_char_1 = xl_col_to_name(col_num_1, 1)
        col_char_2 = xl_col_to_name(col_num_2, 1)
        row_char_1 = '$' + str(row_num_1 + 1)
        row_char_2 = '$' + str(row_num_2 + 1)

        # We need to handle special cases that refer to rows or columns only.
        if row_num_1 == 0 and row_num_2 == self.xls_rowmax - 1:
            range1 = col_char_1
            range2 = col_char_2
            row_col_only = 1
        elif col_num_1 == 0 and col_num_2 == self.xls_colmax - 1:
            range1 = row_char_1
            range2 = row_char_2
            row_col_only = 1
        else:
            range1 = col_char_1 + row_char_1
            range2 = col_char_2 + row_char_2

        # A repeated range is only written once (if it isn't a special case).
        if range1 == range2 and not row_col_only:
            area = range1
        else:
            area = range1 + ':' + range2

        # Build up the print area range "Sheet1!$A$1:$C$13".
        sheetname = self._quote_sheetname(self.name)
        area = sheetname + "!" + area

        return area

    def _sort_pagebreaks(self, breaks):
        # This is an internal method used to filter elements of a list of
        # pagebreaks used in the _store_hbreak() and _store_vbreak() methods.
        # It:
        #   1. Removes duplicate entries from the list.
        #   2. Sorts the list.
        #   3. Removes 0 from the list if present.
        if not breaks:
            return

        breaks_set = set(breaks)

        if 0 in breaks_set:
            breaks_set.remove(0)

        breaks_list = list(breaks_set)
        breaks_list.sort()

        # The Excel 2007 specification says that the maximum number of page
        # breaks is 1026. However, in practice it is actually 1023.
        max_num_breaks = 1023
        if len(breaks_list) > max_num_breaks:
            breaks_list = breaks_list[:max_num_breaks]

        return breaks_list

    def _extract_filter_tokens(self, expression):
        # Extract the tokens from the filter expression. The tokens are mainly
        # non-whitespace groups. The only tricky part is to extract string
        # tokens that contain whitespace and/or quoted double quotes (Excel's
        # escaped quotes).
        #
        # Examples: 'x <  2000'
        #           'x >  2000 and x <  5000'
        #           'x = "foo"'
        #           'x = "foo bar"'
        #           'x = "foo "" bar"'
        #
        if not expression:
            return []

        token_re = re.compile(r'"(?:[^"]|"")*"|\S+')
        tokens = token_re.findall(expression)

        new_tokens = []
        # Remove single leading and trailing quotes and un-escape other quotes.
        for token in tokens:
            if token.startswith('"'):
                token = token[1:]

            if token.endswith('"'):
                token = token[:-1]

            token = token.replace('""', '"')

            new_tokens.append(token)

        return new_tokens

    def _parse_filter_expression(self, expression, tokens):
        # Converts the tokens of a possibly conditional expression into 1 or 2
        # sub expressions for further parsing.
        #
        # Examples:
        #          ('x', '==', 2000) -> exp1
        #          ('x', '>',  2000, 'and', 'x', '<', 5000) -> exp1 and exp2

        if len(tokens) == 7:
            # The number of tokens will be either 3 (for 1 expression)
            # or 7 (for 2  expressions).
            conditional = tokens[3]

            if re.match('(and|&&)', conditional):
                conditional = 0
            elif re.match('(or|\|\|)', conditional):
                conditional = 1
            else:
                warn("Token '%s' is not a valid conditional "
                     "in filter expression '%s'" % (conditional, expression))

            expression_1 = self._parse_filter_tokens(expression, tokens[0:3])
            expression_2 = self._parse_filter_tokens(expression, tokens[4:7])

            return expression_1 + [conditional] + expression_2
        else:
            return self._parse_filter_tokens(expression, tokens)

    def _parse_filter_tokens(self, expression, tokens):
        # Parse the 3 tokens of a filter expression and return the operator
        # and token. The use of numbers instead of operators is a legacy of
        # Spreadsheet::WriteExcel.
        operators = {
            '==': 2,
            '=': 2,
            '=~': 2,
            'eq': 2,

            '!=': 5,
            '!~': 5,
            'ne': 5,
            '<>': 5,

            '<': 1,
            '<=': 3,
            '>': 4,
            '>=': 6,
        }

        operator = operators.get(tokens[1], None)
        token = tokens[2]

        # Special handling of "Top" filter expressions.
        if re.match('top|bottom', tokens[0].lower()):
            value = int(tokens[1])

            if (value < 1 or value > 500):
                warn("The value '%d' in expression '%s' "
                     "must be in the range 1 to 500" % (value, expression))

            token = token.lower()

            if token != 'items' and token != '%':
                warn("The type '%s' in expression '%s' "
                     "must be either 'items' or '%'" % (token, expression))

            if tokens[0].lower() == 'top':
                operator = 30
            else:
                operator = 32

            if tokens[2] == '%':
                operator += 1

            token = str(value)

        if not operator and tokens[0]:
            warn("Token '%s' is not a valid operator "
                 "in filter expression '%s'" % (token[0], expression))

        # Special handling for Blanks/NonBlanks.
        if re.match('blanks|nonblanks', token.lower()):
            # Only allow Equals or NotEqual in this context.
            if operator != 2 and operator != 5:
                warn("The operator '%s' in expression '%s' "
                     "is not valid in relation to Blanks/NonBlanks'"
                     % (tokens[1], expression))

            token = token.lower()

            # The operator should always be 2 (=) to flag a "simple" equality
            # in the binary record. Therefore we convert <> to =.
            if token == 'blanks':
                if operator == 5:
                    token = ' '
            else:
                if operator == 5:
                    operator = 2
                    token = 'blanks'
                else:
                    operator = 5
                    token = ' '

        # if the string token contains an Excel match character then change the
        # operator type to indicate a non "simple" equality.
        if operator == 2 and re.search('[*?]', token):
            operator = 22

        return [operator, token]

    def _encode_password(self, plaintext):
        # Encode the worksheet protection "password" as a simple hash.
        # Based on the algorithm by Daniel Rentz of OpenOffice.
        i = 0
        count = len(plaintext)
        digits = []

        for char in (plaintext):
            i += 1
            char = ord(char) << i
            low_15 = char & 0x7fff
            high_15 = char & 0x7fff << 15
            high_15 = high_15 >> 15
            char = low_15 | high_15
            digits.append(char)

        password_hash = 0x0000

        for digit in digits:
            password_hash ^= digit

        password_hash ^= count
        password_hash ^= 0xCE4B

        return "%X" % password_hash

    def _prepare_image(self, index, image_id, drawing_id, width, height,
                       name, image_type):
        # Set up images/drawings.
        drawing_type = 2
        (row, col, _, x_offset, y_offset, x_scale, y_scale) = \
            self.images[index]

        width *= x_scale
        height *= y_scale

        dimensions = self._position_object_emus(col, row, x_offset, y_offset,
                                                width, height)

        # Convert from pixels to emus.
        width = int(0.5 + (width * 9525))
        height = int(0.5 + (height * 9525))

        # Create a Drawing obj to use with worksheet unless one already exists.
        if not self.drawing:
            drawing = Drawing()
            drawing.embedded = 1
            self.drawing = drawing

            self.external_drawing_links.append(['/drawing',
                                                '../drawings/drawing'
                                                + str(drawing_id)
                                                + '.xml', None])
        else:
            drawing = self.drawing

        drawing_object = [drawing_type]
        drawing_object.extend(dimensions)
        drawing_object.extend([width, height, name, None])

        drawing._add_drawing_object(drawing_object)

        self.drawing_links.append(['/image',
                                   '../media/image'
                                   + str(image_id) + '.'
                                   + image_type])

    def _position_object_emus(self, col_start, row_start, x1, y1,
                              width, height):
        # Calculate the vertices that define the position of a graphical
        # object within the worksheet in EMUs.
        #
        # The vertices are expressed as English Metric Units (EMUs). There are
        # 12,700 EMUs per point. Therefore, 12,700 * 3 /4 = 9,525 EMUs per
        # pixel
        (col_start, row_start, x1, y1,
         col_end, row_end, x2, y2, x_abs, y_abs) = \
            self._position_object_pixels(col_start, row_start, x1, y1,
                                         width, height)

        # Convert the pixel values to EMUs. See above.
        x1 = int(0.5 + 9525 * x1)
        y1 = int(0.5 + 9525 * y1)
        x2 = int(0.5 + 9525 * x2)
        y2 = int(0.5 + 9525 * y2)
        x_abs = int(0.5 + 9525 * x_abs)
        y_abs = int(0.5 + 9525 * y_abs)

        return (col_start, row_start, x1, y1, col_end, row_end, x2, y2,
                x_abs, y_abs)

    # Calculate the vertices that define the position of a graphical object
    # within the worksheet in pixels.
    #
    #         +------------+------------+
    #         |     A      |      B     |
    #   +-----+------------+------------+
    #   |     |(x1,y1)     |            |
    #   |  1  |(A1)._______|______      |
    #   |     |    |              |     |
    #   |     |    |              |     |
    #   +-----+----|    OBJECT    |-----+
    #   |     |    |              |     |
    #   |  2  |    |______________.     |
    #   |     |            |        (B2)|
    #   |     |            |     (x2,y2)|
    #   +---- +------------+------------+
    #
    # Example of an object that covers some of the area from cell A1 to  B2.
    #
    # Based on the width and height of the object we need to calculate 8 vars:
    #
    #     col_start, row_start, col_end, row_end, x1, y1, x2, y2.
    #
    # We also calculate the absolute x and y position of the top left vertex of
    # the object. This is required for images.
    #
    # The width and height of the cells that the object occupies can be
    # variable and have to be taken into account.
    #
    # The values of col_start and row_start are passed in from the calling
    # function. The values of col_end and row_end are calculated by
    # subtracting the width and height of the object from the width and
    # height of the underlying cells.
    #
    def _position_object_pixels(self, col_start, row_start, x1, y1,
                                width, height):
        # col_start       # Col containing upper left corner of object.
        # x1              # Distance to left side of object.
        #
        # row_start       # Row containing top left corner of object.
        # y1              # Distance to top of object.
        #
        # col_end         # Col containing lower right corner of object.
        # x2              # Distance to right side of object.
        #
        # row_end         # Row containing bottom right corner of object.
        # y2              # Distance to bottom of object.
        #
        # width           # Width of object frame.
        # height          # Height of object frame.
        #
        # x_abs           # Absolute distance to left side of object.
        # y_abs           # Absolute distance to top side of object.
        x_abs = 0
        y_abs = 0

        # Calculate the absolute x offset of the top-left vertex.
        if self.col_size_changed:
            for col_id in range(1, col_start + 1):
                x_abs += self._size_col(col_id)
        else:
            # Optimisation for when the column widths haven't changed.
            x_abs += 64 * col_start

        x_abs += x1

        # Calculate the absolute y offset of the top-left vertex.
        # Store the column change to allow optimisations.
        if self.row_size_changed:
            for row_id in range(1, row_start + 1):
                y_abs += self._size_row(row_id)
        else:
            # Optimisation for when the row heights haven't changed.
            y_abs += 20 * row_start

        y_abs += y1

        # Adjust start column for offsets that are greater than the col width.
        while x1 >= self._size_col(col_start):
            x1 -= self._size_col(col_start)
            col_start += 1

        # Adjust start row for offsets that are greater than the row height.
        while y1 >= self._size_row(row_start):
            y1 -= self._size_row(row_start)
            row_start += 1

        # Initialise end cell to the same as the start cell.
        col_end = col_start
        row_end = row_start

        width = width + x1
        height = height + y1

        # Subtract the underlying cell widths to find end cell of the object.
        while width >= self._size_col(col_end):
            width -= self._size_col(col_end)
            col_end += 1

        # Subtract the underlying cell heights to find end cell of the object.

        while height >= self._size_row(row_end):
            height -= self._size_row(row_end)
            row_end += 1

        # TODO, is this required? Write testcase for image that fits cell.
        #
        # The following is only required for positioning drawing/chart objects
        # and not comments. It is probably the result of a bug.
        # if is_drawing:
        #    if width == 0:
        #        col_end -= 1
        #    if height == 0:
        #        row_end -= 1

        # The end vertices are whatever is left from the width and height.
        x2 = width
        y2 = height

        return ([col_start, row_start, x1, y1, col_end, row_end, x2, y2,
                x_abs, y_abs])

    def _size_col(self, col):
        # Convert the width of a cell from user's units to pixels. Excel rounds
        # the column width to the nearest pixel. If the width hasn't been set
        # by the user we use the default value. If the column is hidden it
        # has a value of zero.
        max_digit_width = 7  # For Calabri 11.
        padding = 5
        pixels = 0

        # Look up the cell value to see if it has been changed.
        if col in self.col_sizes:
            width = self.col_sizes[col]

            # Convert to pixels.
            if width == 0:
                pixels = 0
            elif width < 1:
                pixels = int(width * 12 + 0.5)
            else:
                pixels = int(width * max_digit_width + 0.5) + padding
        else:
            pixels = 64

        return pixels

    def _size_row(self, row):
        # Convert the height of a cell from user's units to pixels. If the
        # height hasn't been set by the user we use the default value. If
        #  the row is hidden it has a value of zero.
        pixels = 0

        # Look up the cell value to see if it has been changed
        if row in self.row_sizes:
            height = self.row_sizes[row]

            if height == 0:
                pixels = 0
            else:
                pixels = int(4.0 / 3.0 * height)
        else:
            pixels = int(4.0 / 3.0 * self.default_row_height)

        return pixels

    def _comment_params(self, row, col, string, options):
        # This method handles the additional optional parameters to
        # write_comment() as well as calculating the comment object
        # position and vertices.
        default_width = 128
        default_height = 74

        params = {
            'author': None,
            'color': '#ffffe1',
            'start_cell': None,
            'start_col': None,
            'start_row': None,
            'visible': None,
            'width': default_width,
            'height': default_height,
            'x_offset': None,
            'x_scale': 1,
            'y_offset': None,
            'y_scale': 1,
        }

        # Overwrite the defaults with any user supplied values. Incorrect or
        # misspelled parameters are silently ignored.
        for key in options.keys():
            params[key] = options[key]

        # Ensure that a width and height have been set.
        if not params['width']:
            params['width'] = default_width
        if not params['height']:
            params['height'] = default_height

        # Set the comment background colour.
        params['color'] = xl_color(params['color']).lower()

        # Convert from Excel XML style colour to XML html style colour.
        params['color'] = params['color'].replace('ff', '#', 1)

        # Convert a cell reference to a row and column.
        if params['start_cell'] is not None:
            (start_row, start_col) = xl_cell_to_rowcol(params['start_cell'])
            params['start_row'] = start_row
            params['start_col'] = start_col

        # Set the default start cell and offsets for the comment. These are
        # generally fixed in relation to the parent cell. However there are
        # some edge cases for cells at the, er, edges.
        row_max = self.xls_rowmax
        col_max = self.xls_colmax

        if params['start_row'] is None:
            if row == 0:
                params['start_row'] = 0
            elif row == row_max - 3:
                params['start_row'] = row_max - 7
            elif row == row_max - 2:
                params['start_row'] = row_max - 6
            elif row == row_max - 1:
                params['start_row'] = row_max - 5
            else:
                params['start_row'] = row - 1

        if params['y_offset'] is None:
            if row == 0:
                params['y_offset'] = 2
            elif row == row_max - 3:
                params['y_offset'] = 16
            elif row == row_max - 2:
                params['y_offset'] = 16
            elif row == row_max - 1:
                params['y_offset'] = 14
            else:
                params['y_offset'] = 10

        if params['start_col'] is None:
            if col == col_max - 3:
                params['start_col'] = col_max - 6
            elif col == col_max - 2:
                params['start_col'] = col_max - 5
            elif col == col_max - 1:
                params['start_col'] = col_max - 4
            else:
                params['start_col'] = col + 1

        if params['x_offset'] is None:
            if col == col_max - 3:
                params['x_offset'] = 49
            elif col == col_max - 2:
                params['x_offset'] = 49
            elif col == col_max - 1:
                params['x_offset'] = 49
            else:
                params['x_offset'] = 15

        # Scale the size of the comment box if required.
        if params['x_scale']:
            params['width'] = params['width'] * params['x_scale']

        if params['y_scale']:
            params['height'] = params['height'] * params['y_scale']

        # Round the dimensions to the nearest pixel.
        params['width'] = int(0.5 + params['width'])
        params['height'] = int(0.5 + params['height'])

        # Calculate the positions of comment object.
        vertices = self._position_object_pixels(
            params['start_col'], params['start_row'], params['x_offset'],
            params['y_offset'], params['width'], params['height'])

        # Add the width and height for VML.
        vertices.append(params['width'])
        vertices.append(params['height'])

        return ([row, col, string, params['author'],
                 params['visible'], params['color']] + [vertices])

    def _prepare_vml_objects(self, vml_data_id, vml_shape_id, comment_id):
        comments = []
        # Sort the comments into row/column order for easier comparison
        # testing and set the external links for comments and buttons.
        row_nums = sorted(self.comments.keys())

        for row in row_nums:
            col_nums = sorted(self.comments[row].keys())

            for col in col_nums:
                # Set comment visibility if required and not user defined.
                if self.comments_visible:
                    if self.comments[row][col][4] is None:
                        self.comments[row][col][4] = 1

                # Set comment author if not already user defined.
                if self.comments[row][col][3] is None:
                    self.comments[row][col][3] = self.comments_author

                comments.append(self.comments[row][col])

        self.external_vml_links.append(['/vmlDrawing',
                                        '../drawings/vmlDrawing'
                                        + str(comment_id)
                                        + '.vml'])

        if self.has_comments:
            self.comments_array = comments

            self.external_comment_links.append(['/comments',
                                                '../comments'
                                                + str(comment_id)
                                                + '.xml'])

        count = len(comments)
        start_data_id = vml_data_id

        # The VML o:idmap data id contains a comma separated range when there
        # is more than one 1024 block of comments, like this: data="1,2".
        for i in range(int(count / 1024)):
            vml_data_id = '%s,%d' % (vml_data_id, start_data_id + i + 1)

        self.vml_data_id = vml_data_id
        self.vml_shape_id = vml_shape_id

        return count

    def _is_supported_datetime(self, dt):
        # Determine is an argument is a supported datetime object.
        return(isinstance(dt, datetime.datetime) or
               isinstance(dt, datetime.date) or
               isinstance(dt, datetime.time))

    ###########################################################################
    #
    # The following font methods are, more or less, duplicated from the
    # Styles class. Not the cleanest version of reuse but works for now.
    #
    ###########################################################################
    def _write_font(self, xf_format):
        # Write the <font> element.
        xmlwriter = self.rstring

        xmlwriter._xml_start_tag('rPr')

        # Handle the main font properties.
        if xf_format.bold:
            xmlwriter._xml_empty_tag('b')
        if xf_format.italic:
            xmlwriter._xml_empty_tag('i')
        if xf_format.font_strikeout:
            xmlwriter._xml_empty_tag('strike')
        if xf_format.font_outline:
            xmlwriter._xml_empty_tag('outline')
        if xf_format.font_shadow:
            xmlwriter._xml_empty_tag('shadow')

        # Handle the underline variants.
        if xf_format.underline:
            self._write_underline(xf_format.underline)

        # Handle super/subscript.
        if xf_format.font_script == 1:
            self._write_vert_align('superscript')
        if xf_format.font_script == 2:
            self._write_vert_align('subscript')

        # Write the font size
        xmlwriter._xml_empty_tag('sz', [('val', xf_format.font_size)])

        # Handle colors.
        if xf_format.theme:
            self._write_color('theme', xf_format.theme)
        elif xf_format.color_indexed:
            self._write_color('indexed', xf_format.color_indexed)
        elif xf_format.font_color:
            color = self._get_palette_color(xf_format.font_color)
            self._write_rstring_color('rgb', color)
        else:
            self._write_rstring_color('theme', 1)

        # Write some other font properties related to font families.
        xmlwriter._xml_empty_tag('rFont', [('val', xf_format.font_name)])
        xmlwriter._xml_empty_tag('family', [('val', xf_format.font_family)])

        if xf_format.font_name == 'Calibri' and not xf_format.hyperlink:
            xmlwriter._xml_empty_tag('scheme',
                                     [('val', xf_format.font_scheme)])

        xmlwriter._xml_end_tag('rPr')

    def _write_underline(self, underline):
        # Write the underline font element.
        attributes = []

        # Handle the underline variants.
        if underline == 2:
            attributes = [('val', 'double')]
        elif underline == 33:
            attributes = [('val', 'singleAccounting')]
        elif underline == 34:
            attributes = [('val', 'doubleAccounting')]

        self.rstring._xml_empty_tag('u', attributes)

    def _write_vert_align(self, val):
        # Write the <vertAlign> font sub-element.
        attributes = [('val', val)]

        self.rstring._xml_empty_tag('vertAlign', attributes)

    def _write_rstring_color(self, name, value):
        # Write the <color> element.
        attributes = [(name, value)]

        self.rstring._xml_empty_tag('color', attributes)

    def _get_palette_color(self, color):
        # Convert the RGB color.
        if color[0] == '#':
            color = color[1:]

        return "FF" + color.upper()

    ###########################################################################
    #
    # XML methods.
    #
    ###########################################################################

    def _write_worksheet(self):
        # Write the <worksheet> element. This is the root element.

        schema = 'http://schemas.openxmlformats.org/'
        xmlns = schema + 'spreadsheetml/2006/main'
        xmlns_r = schema + 'officeDocument/2006/relationships'
        xmlns_mc = schema + 'markup-compatibility/2006'
        ms_schema = 'http://schemas.microsoft.com/'
        xmlns_x14ac = ms_schema + 'office/spreadsheetml/2009/9/ac'

        attributes = [
            ('xmlns', xmlns),
            ('xmlns:r', xmlns_r)]

        # Add some extra attributes for Excel 2010. Mainly for sparklines.
        if self.excel_version == 2010:
            attributes.append(('xmlns:mc', xmlns_mc))
            attributes.append(('xmlns:x14ac', xmlns_x14ac))
            attributes.append(('mc:Ignorable', 'x14ac'))

        self._xml_start_tag('worksheet', attributes)

    def _write_dimension(self):
        # Write the <dimension> element. This specifies the range of
        # cells in the worksheet. As a special case, empty
        # spreadsheets use 'A1' as a range.

        if self.dim_rowmin is None and self.dim_colmin is None:
            # If the min dimensions are not defined then no dimensions
            # have been set and we use the default 'A1'.
            ref = 'A1'

        elif self.dim_rowmin is None and self.dim_colmin is not None:
            # If the row dimensions aren't set but the column
            # dimensions are set then they have been changed via
            # set_column().

            if self.dim_colmin == self.dim_colmax:
                # The dimensions are a single cell and not a range.
                ref = xl_rowcol_to_cell(0, self.dim_colmin)
            else:
                # The dimensions are a cell range.
                cell_1 = xl_rowcol_to_cell(0, self.dim_colmin)
                cell_2 = xl_rowcol_to_cell(0, self.dim_colmax)
                ref = cell_1 + ':' + cell_2

        elif (self.dim_rowmin == self.dim_rowmax and
              self.dim_colmin == self.dim_colmax):
            # The dimensions are a single cell and not a range.
            ref = xl_rowcol_to_cell(self.dim_rowmin, self.dim_colmin)
        else:
            # The dimensions are a cell range.
            cell_1 = xl_rowcol_to_cell(self.dim_rowmin, self.dim_colmin)
            cell_2 = xl_rowcol_to_cell(self.dim_rowmax, self.dim_colmax)
            ref = cell_1 + ':' + cell_2

        self._xml_empty_tag('dimension', [('ref', ref)])

    def _write_sheet_views(self):
        # Write the <sheetViews> element.
        self._xml_start_tag('sheetViews')

        # Write the sheetView element.
        self._write_sheet_view()

        self._xml_end_tag('sheetViews')

    def _write_sheet_view(self):
        # Write the <sheetViews> element.
        attributes = []

        # Hide screen gridlines if required
        if not self.screen_gridlines:
            attributes.append(('showGridLines', 0))

        # Hide zeroes in cells.
        if not self.show_zeros:
            attributes.append(('showZeros', 0))

        # Display worksheet right to left for Hebrew, Arabic and others.
        if self.is_right_to_left:
            attributes.append(('rightToLeft', 1))

        # Show that the sheet tab is selected.
        if self.selected:
            attributes.append(('tabSelected', 1))

        # Turn outlines off. Also required in the outlinePr element.
        if not self.outline_on:
            attributes.append(("showOutlineSymbols", 0))

        # Set the page view/layout mode if required.
        if self.page_view:
            attributes.append(('view', 'pageLayout'))

        # Set the zoom level.
        if self.zoom != 100:
            if not self.page_view:
                attributes.append(('zoomScale', self.zoom))
                if self.zoom_scale_normal:
                    attributes.append(('zoomScaleNormal', self.zoom))

        attributes.append(('workbookViewId', 0))

        if self.panes or len(self.selections):
            self._xml_start_tag('sheetView', attributes)
            self._write_panes()
            self._write_selections()
            self._xml_end_tag('sheetView')
        else:
            self._xml_empty_tag('sheetView', attributes)

    def _write_sheet_format_pr(self):
        # Write the <sheetFormatPr> element.
        default_row_height = self.default_row_height
        row_level = self.outline_row_level
        col_level = self.outline_col_level

        attributes = [('defaultRowHeight', default_row_height)]

        if self.default_row_height != 15:
            attributes.append(('customHeight', 1))

        if self.default_row_zeroed:
            attributes.append(('zeroHeight', 1))

        if row_level:
            attributes.append(('outlineLevelRow', row_level))
        if col_level:
            attributes.append(('outlineLevelCol', col_level))

        if self.excel_version == 2010:
            attributes.append(('x14ac:dyDescent', '0.25'))

        self._xml_empty_tag('sheetFormatPr', attributes)

    def _write_cols(self):
        # Write the <cols> element and <col> sub elements.

        # Exit unless some column have been formatted.
        if not self.colinfo:
            return

        self._xml_start_tag('cols')

        for col_info in self.colinfo:
            self._write_col_info(col_info)

        self._xml_end_tag('cols')

    def _write_col_info(self, col_info):
        # Write the <col> element.

        (col_min, col_max, width, cell_format,
         hidden, level, collapsed) = col_info

        custom_width = 1
        xf_index = 0

        # Get the cell_format index.
        if cell_format:
            xf_index = cell_format._get_xf_index()

        # Set the Excel default column width.
        if width is None:
            if not hidden:
                width = 8.43
                custom_width = 0
            else:
                width = 0
        elif width == 8.43:
            # Width is defined but same as default.
            custom_width = 0

        # Convert column width from user units to character width.
        if width > 0:
            # For Calabri 11.
            max_digit_width = 7
            padding = 5
            width = int((float(width) * max_digit_width + padding)
                        / max_digit_width * 256.0) / 256.0

        attributes = [
            ('min', col_min + 1),
            ('max', col_max + 1),
            ('width', width)]

        if xf_index:
            attributes.append(('style', xf_index))
        if hidden:
            attributes.append(('hidden', '1'))
        if custom_width:
            attributes.append(('customWidth', '1'))
        if level:
            attributes.append(('outlineLevel', level))
        if collapsed:
            attributes.append(('collapsed', '1'))

        self._xml_empty_tag('col', attributes)

    def _write_sheet_data(self):
        # Write the <sheetData> element.

        if self.dim_rowmin is None:
            # If the dimensions aren't defined there is no data to write.
            self._xml_empty_tag('sheetData')
        else:
            self._xml_start_tag('sheetData')
            self._write_rows()
            self._xml_end_tag('sheetData')

    def _write_optimized_sheet_data(self):
        # Write the <sheetData> element when the memory optimisation is on.
        # In this case we read the data stored in the temp file and rewrite
        # it to the XML sheet file.
        if self.dim_rowmin is None:
            # If the dimensions aren't defined then there is no data to write.
            self._xml_empty_tag('sheetData')
        else:
            self._xml_start_tag('sheetData')

            # Rewind the filehandle that was used for temp row data.
            buff_size = 65536
            self.row_data_fh.seek(0)
            data = self.row_data_fh.read(buff_size)

            while(data):
                self.fh.write(data)
                data = self.row_data_fh.read(buff_size)

            self.row_data_fh.close()
            os.unlink(self.row_data_filename)

            self._xml_end_tag('sheetData')

    def _write_page_margins(self):
        # Write the <pageMargins> element.
        attributes = [
            ('left', self.margin_left),
            ('right', self.margin_right),
            ('top', self.margin_top),
            ('bottom', self.margin_bottom),
            ('header', self.margin_header),
            ('footer', self.margin_footer)]

        self._xml_empty_tag('pageMargins', attributes)

    def _write_page_setup(self):
        # Write the <pageSetup> element.
        #
        # The following is an example taken from Excel.
        #
        # <pageSetup
        #     paperSize="9"
        #     scale="110"
        #     fitToWidth="2"
        #     fitToHeight="2"
        #     pageOrder="overThenDown"
        #     orientation="portrait"
        #     blackAndWhite="1"
        #     draft="1"
        #     horizontalDpi="200"
        #     verticalDpi="200"
        #     r:id="rId1"
        # />
        #
        attributes = []

        # Skip this element if no page setup has changed.
        if not self.page_setup_changed:
            return

        # Set paper size.
        if self.paper_size:
            attributes.append(('paperSize', self.paper_size))

        # Set the print_scale.
        if self.print_scale != 100:
            attributes.append(('scale', self.print_scale))

        # Set the "Fit to page" properties.
        if self.fit_page and self.fit_width != 1:
            attributes.append(('fitToWidth', self.fit_width))

        if self.fit_page and self.fit_height != 1:
            attributes.append(('fitToHeight', self.fit_height))

        # Set the page print direction.
        if self.page_order:
            attributes.append(('pageOrder', "overThenDown"))

        # Set page orientation.
        if self.orientation:
            attributes.append(('orientation', 'portrait'))
        else:
            attributes.append(('orientation', 'landscape'))

        # Set start page for printing.
        if self.page_start != 0:
            attributes.append(('useFirstPageNumber', self.page_start))

        self._xml_empty_tag('pageSetup', attributes)

    def _write_print_options(self):
        # Write the <printOptions> element.
        attributes = []

        if not self.print_options_changed:
            return

        # Set horizontal centering.
        if self.hcenter:
            attributes.append(('horizontalCentered', 1))

        # Set vertical centering.
        if self.vcenter:
            attributes.append(('verticalCentered', 1))

        # Enable row and column headers.
        if self.print_headers:
            attributes.append(('headings', 1))

        # Set printed gridlines.
        if self.print_gridlines:
            attributes.append(('gridLines', 1))

        self._xml_empty_tag('printOptions', attributes)

    def _write_header_footer(self):
        # Write the <headerFooter> element.

        if not self.header_footer_changed:
            return

        self._xml_start_tag('headerFooter')

        if self.header:
            self._write_odd_header()
        if self.footer:
            self._write_odd_footer()

        self._xml_end_tag('headerFooter')

    def _write_odd_header(self):
        # Write the <headerFooter> element.
        self._xml_data_element('oddHeader', self.header)

    def _write_odd_footer(self):
        # Write the <headerFooter> element.
        self._xml_data_element('oddFooter', self.footer)

    def _write_rows(self):
        # Write out the worksheet data as a series of rows and cells.
        self._calculate_spans()

        for row_num in range(self.dim_rowmin, self.dim_rowmax + 1):

            if (row_num in self.set_rows or row_num in self.comments
                    or self.table[row_num]):
                # Only process rows with formatting, cell data and/or comments.

                span_index = int(row_num / 16)

                if span_index in self.row_spans:
                    span = self.row_spans[span_index]
                else:
                    span = None

                if self.table[row_num]:
                    # Write the cells if the row contains data.
                    if row_num not in self.set_rows:
                        self._write_row(row_num, span)
                    else:
                        self._write_row(row_num, span, self.set_rows[row_num])

                    for col_num in range(self.dim_colmin, self.dim_colmax + 1):
                        if col_num in self.table[row_num]:
                            col_ref = self.table[row_num][col_num]
                            self._write_cell(row_num, col_num, col_ref)

                    self._xml_end_tag('row')

                elif row_num in self.comments:
                    # Row with comments in cells.
                    self._write_empty_row(row_num, span,
                                          self.set_rows[row_num])
                else:
                    # Blank row with attributes only.
                    self._write_empty_row(row_num, span,
                                          self.set_rows[row_num])

    def _write_single_row(self, current_row_num=0):
        # Write out the worksheet data as a single row with cells.
        # This method is used when memory optimisation is on. A single
        # row is written and the data table is reset. That way only
        # one row of data is kept in memory at any one time. We don't
        # write span data in the optimised case since it is optional.

        # Set the new previous row as the current row.
        row_num = self.previous_row
        self.previous_row = current_row_num

        if (row_num in self.set_rows or row_num in self.comments
                or self.table[row_num]):
            # Only process rows with formatting, cell data and/or comments.

            # No span data in optimised mode.
            span = None

            if self.table[row_num]:
                # Write the cells if the row contains data.
                if row_num not in self.set_rows:
                    self._write_row(row_num, span)
                else:
                    self._write_row(row_num, span, self.set_rows[row_num])

                for col_num in range(self.dim_colmin, self.dim_colmax + 1):
                    if col_num in self.table[row_num]:
                        col_ref = self.table[row_num][col_num]
                        self._write_cell(row_num, col_num, col_ref)

                self._xml_end_tag('row')
            else:
                # Row attributes or comments only.
                self._write_empty_row(row_num, span, self.set_rows[row_num])

        # Reset table.
        self.table.clear()

    def _calculate_spans(self):
        # Calculate the "spans" attribute of the <row> tag. This is an
        # XLSX optimisation and isn't strictly required. However, it
        # makes comparing files easier. The span is the same for each
        # block of 16 rows.
        spans = {}
        span_min = None
        span_max = None

        for row_num in range(self.dim_rowmin, self.dim_rowmax + 1):

            if row_num in self.table:
                # Calculate spans for cell data.
                for col_num in range(self.dim_colmin, self.dim_colmax + 1):
                    if col_num in self.table[row_num]:
                        if span_min is None:
                            span_min = col_num
                            span_max = col_num
                        else:
                            if col_num < span_min:
                                span_min = col_num
                            if col_num > span_max:
                                span_max = col_num

            if row_num in self.comments:
                # Calculate spans for comments.
                for col_num in range(self.dim_colmin, self.dim_colmax + 1):
                    if (row_num in self.comments
                            and col_num in self.comments[row_num]):
                        if span_min is None:
                            span_min = col_num
                            span_max = col_num
                        else:
                            if col_num < span_min:
                                span_min = col_num
                            if col_num > span_max:
                                span_max = col_num

            if ((row_num + 1) % 16 == 0) or row_num == self.dim_rowmax:
                span_index = int(row_num / 16)

                if span_min is not None:
                    span_min += 1
                    span_max += 1
                    spans[span_index] = "%s:%s" % (span_min, span_max)
                    span_min = None

        self.row_spans = spans

    def _write_row(self, row, spans, properties=None, empty_row=False):
        # Write the <row> element.
        xf_index = 0

        if properties:
            height, cell_format, hidden, level, collapsed = properties
        else:
            height, cell_format, hidden, level, collapsed = None, None, 0, 0, 0

        if height is None:
            height = self.default_row_height

        attributes = [('r', row + 1)]

        # Get the cell_format index.
        if cell_format:
            xf_index = cell_format._get_xf_index()

        # Add row attributes where applicable.
        if spans:
            attributes.append(('spans', spans))
        if xf_index:
            attributes.append(('s', xf_index))
        if cell_format:
            attributes.append(('customFormat', 1))
        if height != 15:
            attributes.append(('ht', height))
        if hidden:
            attributes.append(('hidden', 1))
        if height != 15:
            attributes.append(('customHeight', 1))
        if level:
            attributes.append(('outlineLevel', level))
        if collapsed:
            attributes.append(('collapsed', 1))
        if self.excel_version == 2010:
            attributes.append(('x14ac:dyDescent', '0.25'))

        if empty_row:
            self._xml_empty_tag_unencoded('row', attributes)
        else:
            self._xml_start_tag_unencoded('row', attributes)

    def _write_empty_row(self, *args):
        # Write and empty <row> element.
        self._write_row(*args, empty_row=True)

    def _write_cell(self, row, col, cell):
        # Write the <cell> element.
        #
        # Note. This is the innermost loop so efficiency is important.
        cell_range = xl_rowcol_to_cell(row, col)

        attributes = [('r', cell_range)]

        if cell.format:
            # Add the cell format index.
            xf_index = cell.format._get_xf_index()
            attributes.append(('s', xf_index))
        elif row in self.set_rows and self.set_rows[row][1]:
            # Add the row format.
            row_xf = self.set_rows[row][1]
            attributes.append(('s', row_xf._get_xf_index()))
        elif col in self.col_formats:
            # Add the column format.
            col_xf = self.col_formats[col]
            attributes.append(('s', col_xf._get_xf_index()))

        # Write the various cell types.
        if type(cell).__name__ == 'Number':
            # Write a number.
            self._xml_number_element(cell.number, attributes)

        elif type(cell).__name__ == 'String':
            # Write a string.
            string = cell.string

            if not self.optimization:
                # Write a shared string.
                self._xml_string_element(string, attributes)
            else:
                # Write an optimised in-line string.

                # Escape control characters. See SharedString.pm for details.
                string = re.sub('(_x[0-9a-fA-F]{4}_)', r'_x005F\1', string)
                string = re.sub(r'([\x00-\x08\x0B-\x1F])',
                                lambda match: "_x%04X_" %
                                ord(match.group(1)), string)

                # Write any rich strings without further tags.
                if re.search('^<r>', string) and re.search('</r>$', string):
                    self._xml_rich_inline_string(string, attributes)
                else:
                    # Add attribute to preserve leading or trailing whitespace.
                    preserve = 0
                    if re.search('^\s', string) or re.search('\s$', string):
                        preserve = 1

                    self._xml_inline_string(string, preserve, attributes)

        elif type(cell).__name__ == 'Formula':
            # Write a formula. First check if the formula value is a string.
            try:
                float(cell.value)
            except ValueError:
                attributes.append(('t', 'str'))

            self._xml_formula_element(cell.formula, cell.value, attributes)

        elif type(cell).__name__ == 'ArrayFormula':
            # Write a array formula.

            # First check if the formula value is a string.
            try:
                float(cell.value)
            except ValueError:
                attributes.append(('t', 'str'))

            # Write an array formula.
            self._xml_start_tag('c', attributes)
            self._write_cell_array_formula(cell.formula, cell.range)
            self._write_cell_value(cell.value)
            self._xml_end_tag('c')

        elif type(cell).__name__ == 'Blank':
            # Write a empty cell.
            self._xml_empty_tag('c', attributes)

    def _write_cell_value(self, value):
        # Write the cell value <v> element.
        if value is None:
            value = ''

        self._xml_data_element('v', value)

    def _write_cell_array_formula(self, formula, cell_range):
        # Write the cell array formula <f> element.
        attributes = [
            ('t', 'array'),
            ('ref', cell_range)
        ]

        self._xml_data_element('f', formula, attributes)

    def _write_sheet_pr(self):
        # Write the <sheetPr> element for Sheet level properties.
        attributes = []

        if (not self.fit_page
                and not self.filter_on
                and not self.tab_color
                and not self.outline_changed
                and not self.vba_codename):
            return

        if self.vba_codename:
            attributes.append(('codeName', self.vba_codename))

        if self.filter_on:
            attributes.append(('filterMode', 1))

        if (self.fit_page
                or self.tab_color
                or self.outline_changed):
            self._xml_start_tag('sheetPr', attributes)
            self._write_tab_color()
            self._write_outline_pr()
            self._write_page_set_up_pr()
            self._xml_end_tag('sheetPr')
        else:
            self._xml_empty_tag('sheetPr', attributes)

    def _write_page_set_up_pr(self):
        # Write the <pageSetUpPr> element.
        if not self.fit_page:
            return

        attributes = [('fitToPage', 1)]
        self._xml_empty_tag('pageSetUpPr', attributes)

    def _write_tab_color(self):
        # Write the <tabColor> element.
        color = self.tab_color

        if not color:
            return

        attributes = [('rgb', color)]

        self._xml_empty_tag('tabColor', attributes)

    def _write_outline_pr(self):
        # Write the <outlinePr> element.
        attributes = []

        if not self.outline_changed:
            return

        if self.outline_style:
            attributes.append(("applyStyles", 1))
        if not self.outline_below:
            attributes.append(("summaryBelow", 0))
        if not self.outline_right:
            attributes.append(("summaryRight", 0))
        if not self.outline_on:
            attributes.append(("showOutlineSymbols", 0))

        self._xml_empty_tag('outlinePr', attributes)

    def _write_row_breaks(self):
        # Write the <rowBreaks> element.
        page_breaks = self._sort_pagebreaks(self.hbreaks)

        if not page_breaks:
            return

        count = len(page_breaks)

        attributes = [
            ('count', count),
            ('manualBreakCount', count),
        ]

        self._xml_start_tag('rowBreaks', attributes)

        for row_num in (page_breaks):
            self._write_brk(row_num, 16383)

        self._xml_end_tag('rowBreaks')

    def _write_col_breaks(self):
        # Write the <colBreaks> element.
        page_breaks = self._sort_pagebreaks(self.vbreaks)

        if not page_breaks:
            return

        count = len(page_breaks)

        attributes = [
            ('count', count),
            ('manualBreakCount', count),
        ]

        self._xml_start_tag('colBreaks', attributes)

        for col_num in (page_breaks):
            self._write_brk(col_num, 1048575)

        self._xml_end_tag('colBreaks')

    def _write_brk(self, brk_id, brk_max):
        # Write the <brk> element.
        attributes = [
            ('id', brk_id),
            ('max', brk_max),
            ('man', 1)]

        self._xml_empty_tag('brk', attributes)

    def _write_merge_cells(self):
        # Write the <mergeCells> element.
        merged_cells = self.merge
        count = len(merged_cells)

        if not count:
            return

        attributes = [('count', count)]

        self._xml_start_tag('mergeCells', attributes)

        for merged_range in (merged_cells):

            # Write the mergeCell element.
            self._write_merge_cell(merged_range)

        self._xml_end_tag('mergeCells')

    def _write_merge_cell(self, merged_range):
        # Write the <mergeCell> element.
        (row_min, col_min, row_max, col_max) = merged_range

        # Convert the merge dimensions to a cell range.
        cell_1 = xl_rowcol_to_cell(row_min, col_min)
        cell_2 = xl_rowcol_to_cell(row_max, col_max)
        ref = cell_1 + ':' + cell_2

        attributes = [('ref', ref)]

        self._xml_empty_tag('mergeCell', attributes)

    def _write_hyperlinks(self):
        # Process any stored hyperlinks in row/col order and write the
        # <hyperlinks> element. The attributes are different for internal
        # and external links.
        hlink_refs = []
        display = None

        # Sort the hyperlinks into row order.
        row_nums = sorted(self.hyperlinks.keys())

        # Exit if there are no hyperlinks to process.
        if not row_nums:
            return

        # Iterate over the rows.
        for row_num in (row_nums):
            # Sort the hyperlinks into column order.
            col_nums = sorted(self.hyperlinks[row_num].keys())

            # Iterate over the columns.
            for col_num in (col_nums):
                # Get the link data for this cell.
                link = self.hyperlinks[row_num][col_num]
                link_type = link["link_type"]

                # If the cell isn't a string then we have to add the url as
                # the string to display.
                if (self.table
                        and self.table[row_num]
                        and self.table[row_num][col_num]):
                    cell = self.table[row_num][col_num]
                    if type(cell).__name__ != 'String':
                        display = link["url"]

                if link_type == 1:
                    # External link with rel file relationship.
                    self.rel_count += 1

                    hlink_refs.append([link_type,
                                       row_num,
                                       col_num,
                                       self.rel_count,
                                       link["str"],
                                       display,
                                       link["tip"]])

                    # Links for use by the packager.
                    self.external_hyper_links.append(['/hyperlink',
                                                      link["url"], 'External'])
                else:
                    # Internal link with rel file relationship.
                    hlink_refs.append([link_type,
                                       row_num,
                                       col_num,
                                       link["url"],
                                       link["str"],
                                       link["tip"]])

        # Write the hyperlink elements.
        self._xml_start_tag('hyperlinks')

        for args in (hlink_refs):
            link_type = args.pop(0)

            if link_type == 1:
                self._write_hyperlink_external(*args)
            elif link_type == 2:
                self._write_hyperlink_internal(*args)

        self._xml_end_tag('hyperlinks')

    def _write_hyperlink_external(self, row, col, id_num, location=None,
                                  display=None, tooltip=None):
        # Write the <hyperlink> element for external links.
        ref = xl_rowcol_to_cell(row, col)
        r_id = 'rId' + str(id_num)

        attributes = [
            ('ref', ref),
            ('r:id', r_id)]

        if location is not None:
            attributes.append(('location', location))
        if display is not None:
            attributes.append(('display', display))
        if tooltip is not None:
            attributes.append(('tooltip', tooltip))

        self._xml_empty_tag('hyperlink', attributes)

    def _write_hyperlink_internal(self, row, col, location=None, display=None,
                                  tooltip=None):
        # Write the <hyperlink> element for internal links.
        ref = xl_rowcol_to_cell(row, col)

        attributes = [
            ('ref', ref),
            ('location', location)]

        if tooltip is not None:
            attributes.append(('tooltip', tooltip))
        attributes.append(('display', display))

        self._xml_empty_tag('hyperlink', attributes)

    def _write_auto_filter(self):
        # Write the <autoFilter> element.
        if not self.autofilter_ref:
            return

        attributes = [('ref', self.autofilter_ref)]

        if self.filter_on:
            # Autofilter defined active filters.
            self._xml_start_tag('autoFilter', attributes)
            self._write_autofilters()
            self._xml_end_tag('autoFilter')

        else:
            # Autofilter defined without active filters.
            self._xml_empty_tag('autoFilter', attributes)

    def _write_autofilters(self):
        # Function to iterate through the columns that form part of an
        # autofilter range and write the appropriate filters.
        (col1, col2) = self.filter_range

        for col in range(col1, col2 + 1):
            # Skip if column doesn't have an active filter.
            if not col in self.filter_cols:
                continue

            # Retrieve the filter tokens and write the autofilter records.
            tokens = self.filter_cols[col]
            filter_type = self.filter_type[col]

            # Filters are relative to first column in the autofilter.
            self._write_filter_column(col - col1, filter_type, tokens)

    def _write_filter_column(self, col_id, filter_type, filters):
        # Write the <filterColumn> element.
        attributes = [('colId', col_id)]

        self._xml_start_tag('filterColumn', attributes)

        if filter_type == 1:
            # Type == 1 is the new XLSX style filter.
            self._write_filters(filters)
        else:
            # Type == 0 is the classic "custom" filter.
            self._write_custom_filters(filters)

        self._xml_end_tag('filterColumn')

    def _write_filters(self, filters):
        # Write the <filters> element.

        if len(filters) == 1 and filters[0] == 'blanks':
            # Special case for blank cells only.
            self._xml_empty_tag('filters', [('blank', 1)])
        else:
            # General case.
            self._xml_start_tag('filters')

            for autofilter in (filters):
                self._write_filter(autofilter)

            self._xml_end_tag('filters')

    def _write_filter(self, val):
        # Write the <filter> element.
        attributes = [('val', val)]

        self._xml_empty_tag('filter', attributes)

    def _write_custom_filters(self, tokens):
        # Write the <customFilters> element.
        if len(tokens) == 2:
            # One filter expression only.
            self._xml_start_tag('customFilters')
            self._write_custom_filter(*tokens)
            self._xml_end_tag('customFilters')
        else:
            # Two filter expressions.
            attributes = []

            # Check if the "join" operand is "and" or "or".
            if tokens[2] == 0:
                attributes = [('and', 1)]
            else:
                attributes = [('and', 0)]

            # Write the two custom filters.
            self._xml_start_tag('customFilters', attributes)
            self._write_custom_filter(tokens[0], tokens[1])
            self._write_custom_filter(tokens[3], tokens[4])
            self._xml_end_tag('customFilters')

    def _write_custom_filter(self, operator, val):
        # Write the <customFilter> element.
        attributes = []

        operators = {
            1: 'lessThan',
            2: 'equal',
            3: 'lessThanOrEqual',
            4: 'greaterThan',
            5: 'notEqual',
            6: 'greaterThanOrEqual',
            22: 'equal',
        }

        # Convert the operator from a number to a descriptive string.
        if operators[operator] is not None:
            operator = operators[operator]
        else:
            warn("Unknown operator = %s" % operator)

        # The 'equal' operator is the default attribute and isn't stored.
        if not operator == 'equal':
            attributes.append(('operator', operator))
        attributes.append(('val', val))

        self._xml_empty_tag('customFilter', attributes)

    def _write_sheet_protection(self):
        # Write the <sheetProtection> element.
        attributes = []

        if not self.protect_options:
            return

        options = self.protect_options

        if options['password']:
            attributes.append(('password', options['password']))
        if options['sheet']:
            attributes.append(('sheet', 1))
        if options['content']:
            attributes.append(('content', 1))
        if not options['objects']:
            attributes.append(('objects', 1))
        if not options['scenarios']:
            attributes.append(('scenarios', 1))
        if options['format_cells']:
            attributes.append(('formatCells', 0))
        if options['format_columns']:
            attributes.append(('formatColumns', 0))
        if options['format_rows']:
            attributes.append(('formatRows', 0))
        if options['insert_columns']:
            attributes.append(('insertColumns', 0))
        if options['insert_rows']:
            attributes.append(('insertRows', 0))
        if options['insert_hyperlinks']:
            attributes.append(('insertHyperlinks', 0))
        if options['delete_columns']:
            attributes.append(('deleteColumns', 0))
        if options['delete_rows']:
            attributes.append(('deleteRows', 0))
        if not options['select_locked_cells']:
            attributes.append(('selectLockedCells', 1))
        if options['sort']:
            attributes.append(('sort', 0))
        if options['autofilter']:
            attributes.append(('autoFilter', 0))
        if options['pivot_tables']:
            attributes.append(('pivotTables', 0))
        if not options['select_unlocked_cells']:
            attributes.append(('selectUnlockedCells', 1))

        self._xml_empty_tag('sheetProtection', attributes)

    def _write_drawings(self):
        # Write the <drawing> elements.
        if not self.drawing:
            return

        self._write_drawing(self.rel_count + 1)

    def _write_drawing(self, drawing_id):
        # Write the <drawing> element.
        r_id = 'rId' + str(drawing_id)

        attributes = [('r:id', r_id)]

        self._xml_empty_tag('drawing', attributes)

    def _write_legacy_drawing(self):
        # Write the <legacyDrawing> element.
        if not self.has_vml:
            return

        # Increment the relationship id for any drawings or comments.
        self.rel_count += 1
        r_id = str(self.rel_count)

        attributes = [('r:id', 'rId' + r_id)]

        self._xml_empty_tag('legacyDrawing', attributes)

    def _write_data_validations(self):
        # Write the <dataValidations> element.
        validations = self.validations
        count = len(validations)

        if not count:
            return

        attributes = [('count', count)]

        self._xml_start_tag('dataValidations', attributes)

        for validation in (validations):

            # Write the dataValidation element.
            self._write_data_validation(validation)

        self._xml_end_tag('dataValidations')

    def _write_data_validation(self, options):
        # Write the <dataValidation> element.
        sqref = ''
        attributes = []

        # Set the cell range(s) for the data validation.
        for cells in options['cells']:

            # Add a space between multiple cell ranges.
            if sqref != '':
                sqref += ' '

            (row_first, col_first, row_last, col_last) = cells

            # Swap last row/col for first row/col as necessary
            if row_first > row_last:
                (row_first, row_last) = (row_last, row_first)

            if col_first > col_last:
                (col_first, col_last) = (col_last, col_first)

            # If the first and last cell are the same write a single cell.
            if (row_first == row_last) and (col_first == col_last):
                sqref += xl_rowcol_to_cell(row_first, col_first)
            else:
                sqref += xl_range(row_first, col_first, row_last, col_last)

        attributes.append(('type', options['validate']))

        if options['criteria'] != 'between':
            attributes.append(('operator', options['criteria']))

        if 'error_type' in options:
            if options['error_type'] == 1:
                attributes.append(('errorStyle', 'warning'))
            if options['error_type'] == 2:
                attributes.append(('errorStyle', 'information'))

        if options['ignore_blank']:
            attributes.append(('allowBlank', 1))

        if not options['dropdown']:
            attributes.append(('showDropDown', 1))

        if options['show_input']:
            attributes.append(('showInputMessage', 1))

        if options['show_error']:
            attributes.append(('showErrorMessage', 1))

        if 'error_title' in options:
            attributes.append(('errorTitle', options['error_title']))

        if 'error_message' in options:
            attributes.append(('error', options['error_message']))

        if 'input_title' in options:
            attributes.append(('promptTitle', options['input_title']))

        if 'input_message' in options:
            attributes.append(('prompt', options['input_message']))

        attributes.append(('sqref', sqref))

        self._xml_start_tag('dataValidation', attributes)

        # Write the formula1 element.
        self._write_formula_1(options['value'])

        # Write the formula2 element.
        if options['maximum'] is not None:
            self._write_formula_2(options['maximum'])

        self._xml_end_tag('dataValidation')

    def _write_formula_1(self, formula):
        # Write the <formula1> element.

        if type(formula) is list:
            formula = ','.join([str(item) for item in formula])
            formula = '"%s"' % formula
        else:
            # Check if the formula is a number.
            try:
                float(formula)
            except ValueError:
                # Not a number. Remove the formula '=' sign if it exists.
                if formula.startswith('='):
                    formula = formula.lstrip('=')

        self._xml_data_element('formula1', formula)

    def _write_formula_2(self, formula):
        # Write the <formula2> element.

        # Check if the formula is a number.
        try:
            float(formula)
        except ValueError:
            # Not a number. Remove the formula '=' sign if it exists.
            if formula.startswith('='):
                formula = formula.lstrip('=')

        self._xml_data_element('formula2', formula)

    def _write_conditional_formats(self):
        # Write the Worksheet conditional formats.
        ranges = sorted(self.cond_formats.keys())

        if not ranges:
            return

        for cond_range in (ranges):
            self._write_conditional_formatting(cond_range,
                                               self.cond_formats[cond_range])

    def _write_conditional_formatting(self, cond_range, params):
        # Write the <conditionalFormatting> element.
        attributes = [('sqref', cond_range)]
        self._xml_start_tag('conditionalFormatting', attributes)
        for param in (params):
            # Write the cfRule element.
            self._write_cf_rule(param)
        self._xml_end_tag('conditionalFormatting')

    def _write_cf_rule(self, params):
        # Write the <cfRule> element.
        attributes = [('type', params['type'])]

        if 'format' in params and params['format'] is not None:
            attributes.append(('dxfId', params['format']))

        attributes.append(('priority', params['priority']))

        if params['type'] == 'cellIs':
            attributes.append(('operator', params['criteria']))

            self._xml_start_tag('cfRule', attributes)

            if 'minimum' in params and 'maximum' in params:
                self._write_formula(params['minimum'])
                self._write_formula(params['maximum'])
            else:
                self._write_formula(params['value'])

            self._xml_end_tag('cfRule')

        elif params['type'] == 'aboveAverage':
            if re.search('below', params['criteria']):
                attributes.append(('aboveAverage', 0))

            if re.search('equal', params['criteria']):
                attributes.append(('equalAverage', 1))

            if re.search('[123] std dev', params['criteria']):
                match = re.search('([123]) std dev', params['criteria'])
                attributes.append(('stdDev', match.group(1)))

            self._xml_empty_tag('cfRule', attributes)

        elif params['type'] == 'top10':
            if 'criteria' in params and params['criteria'] == '%':
                attributes.append(('percent', 1))

            if 'direction' in params:
                attributes.append(('bottom', 1))

            rank = params['value'] or 10
            attributes.append(('rank', rank))

            self._xml_empty_tag('cfRule', attributes)

        elif params['type'] == 'duplicateValues':
            self._xml_empty_tag('cfRule', attributes)

        elif params['type'] == 'uniqueValues':
            self._xml_empty_tag('cfRule', attributes)

        elif (params['type'] == 'containsText'
              or params['type'] == 'notContainsText'
              or params['type'] == 'beginsWith'
              or params['type'] == 'endsWith'):
            attributes.append(('operator', params['criteria']))
            attributes.append(('text', params['value']))
            self._xml_start_tag('cfRule', attributes)
            self._write_formula(params['formula'])
            self._xml_end_tag('cfRule')

        elif params['type'] == 'timePeriod':
            attributes.append(('timePeriod', params['criteria']))
            self._xml_start_tag('cfRule', attributes)
            self._write_formula(params['formula'])
            self._xml_end_tag('cfRule')

        elif (params['type'] == 'containsBlanks'
              or params['type'] == 'notContainsBlanks'
              or params['type'] == 'containsErrors'
              or params['type'] == 'notContainsErrors'):
            self._xml_start_tag('cfRule', attributes)
            self._write_formula(params['formula'])
            self._xml_end_tag('cfRule')

        elif params['type'] == 'colorScale':
            self._xml_start_tag('cfRule', attributes)
            self._write_color_scale(params)
            self._xml_end_tag('cfRule')

        elif params['type'] == 'dataBar':
            self._xml_start_tag('cfRule', attributes)
            self._write_data_bar(params)
            self._xml_end_tag('cfRule')

        elif params['type'] == 'expression':
            self._xml_start_tag('cfRule', attributes)
            self._write_formula(params['criteria'])
            self._xml_end_tag('cfRule')

    def _write_formula(self, formula):
        # Write the <formula> element.

        # Check if the formula is a number.
        try:
            float(formula)
        except ValueError:
            # Not a number. Remove the formula '=' sign if it exists.
            if formula.startswith('='):
                formula = formula.lstrip('=')

        self._xml_data_element('formula', formula)

    def _write_color_scale(self, param):
        # Write the <colorScale> element.

        self._xml_start_tag('colorScale')

        self._write_cfvo(param['min_type'], param['min_value'])

        if param['mid_type'] is not None:
            self._write_cfvo(param['mid_type'], param['mid_value'])

        self._write_cfvo(param['max_type'], param['max_value'])

        self._write_color('rgb', param['min_color'])

        if param['mid_color'] is not None:
            self._write_color('rgb', param['mid_color'])

        self._write_color('rgb', param['max_color'])

        self._xml_end_tag('colorScale')

    def _write_data_bar(self, param):
        # Write the <dataBar> element.
        self._xml_start_tag('dataBar')

        self._write_cfvo(param['min_type'], param['min_value'])
        self._write_cfvo(param['max_type'], param['max_value'])
        self._write_color('rgb', param['bar_color'])

        self._xml_end_tag('dataBar')

    def _write_cfvo(self, cf_type, val):
        # Write the <cfvo> element.
        attributes = [('type', cf_type), ('val', val)]

        self._xml_empty_tag('cfvo', attributes)

    def _write_color(self, name, value):
        # Write the <color> element.
        attributes = [(name, value)]

        self._xml_empty_tag('color', attributes)

    def _write_selections(self):
        # Write the <selection> elements.
        for selection in self.selections:
            self._write_selection(*selection)

    def _write_selection(self, pane, active_cell, sqref):
        # Write the <selection> element.
        attributes = []

        if pane:
            attributes.append(('pane', pane))

        if active_cell:
            attributes.append(('activeCell', active_cell))

        if sqref:
            attributes.append(('sqref', sqref))

        self._xml_empty_tag('selection', attributes)

    def _write_panes(self):
        # Write the frozen or split <pane> elements.
        panes = self.panes

        if not len(panes):
            return

        if panes[4] == 2:
            self._write_split_panes(*panes)
        else:
            self._write_freeze_panes(*panes)

    def _write_freeze_panes(self, row, col, top_row, left_col, pane_type):
        # Write the <pane> element for freeze panes.
        attributes = []

        y_split = row
        x_split = col
        top_left_cell = xl_rowcol_to_cell(top_row, left_col)
        active_pane = ''
        state = ''
        active_cell = ''
        sqref = ''

        # Move user cell selection to the panes.
        if self.selections:
            (_, active_cell, sqref) = self.selections[0]
            self.selections = []

        # Set the active pane.
        if row and col:
            active_pane = 'bottomRight'

            row_cell = xl_rowcol_to_cell(row, 0)
            col_cell = xl_rowcol_to_cell(0, col)

            self.selections.append(['topRight', col_cell, col_cell])
            self.selections.append(['bottomLeft', row_cell, row_cell])
            self.selections.append(['bottomRight', active_cell, sqref])

        elif col:
            active_pane = 'topRight'
            self.selections.append(['topRight', active_cell, sqref])

        else:
            active_pane = 'bottomLeft'
            self.selections.append(['bottomLeft', active_cell, sqref])

        # Set the pane type.
        if pane_type == 0:
            state = 'frozen'
        elif pane_type == 1:
            state = 'frozenSplit'
        else:
            state = 'split'

        if x_split:
            attributes.append(('xSplit', x_split))

        if y_split:
            attributes.append(('ySplit', y_split))

        attributes.append(('topLeftCell', top_left_cell))
        attributes.append(('activePane', active_pane))
        attributes.append(('state', state))

        self._xml_empty_tag('pane', attributes)

    def _write_split_panes(self, row, col, top_row, left_col, pane_type):
        # Write the <pane> element for split panes.
        attributes = []
        has_selection = 0
        active_pane = ''
        active_cell = ''
        sqref = ''

        y_split = row
        x_split = col

        # Move user cell selection to the panes.
        if self.selections:
            (_, active_cell, sqref) = self.selections[0]
            self.selections = []
            has_selection = 1

        # Convert the row and col to 1/20 twip units with padding.
        if y_split:
            y_split = int(20 * y_split + 300)

        if x_split:
            x_split = self._calculate_x_split_width(x_split)

        # For non-explicit topLeft definitions, estimate the cell offset based
        # on the pixels dimensions. This is only a workaround and doesn't take
        # adjusted cell dimensions into account.
        if top_row == row and left_col == col:
            top_row = int(0.5 + (y_split - 300) / 20 / 15)
            left_col = int(0.5 + (x_split - 390) / 20 / 3 * 4 / 64)

        top_left_cell = xl_rowcol_to_cell(top_row, left_col)

        # If there is no selection set the active cell to the top left cell.
        if not has_selection:
            active_cell = top_left_cell
            sqref = top_left_cell

        # Set the Cell selections.
        if row and col:
            active_pane = 'bottomRight'

            row_cell = xl_rowcol_to_cell(top_row, 0)
            col_cell = xl_rowcol_to_cell(0, left_col)

            self.selections.append(['topRight', col_cell, col_cell])
            self.selections.append(['bottomLeft', row_cell, row_cell])
            self.selections.append(['bottomRight', active_cell, sqref])

        elif col:
            active_pane = 'topRight'
            self.selections.append(['topRight', active_cell, sqref])

        else:
            active_pane = 'bottomLeft'
            self.selections.append(['bottomLeft', active_cell, sqref])

        # Format splits to the same precision as Excel.
        if x_split:
            attributes.append(('xSplit', "%.15g" % x_split))

        if y_split:
            attributes.append(('ySplit', "%.15g" % y_split))

        attributes.append(('topLeftCell', top_left_cell))

        if has_selection:
            attributes.append(('activePane', active_pane))

        self._xml_empty_tag('pane', attributes)

    def _calculate_x_split_width(self, width):
        # Convert column width from user units to pane split width.

        max_digit_width = 7  # For Calabri 11.
        padding = 5

        # Convert to pixels.
        if width < 1:
            pixels = int(width * 12 + 0.5)
        else:
            pixels = int(width * max_digit_width + 0.5) + padding

        # Convert to points.
        points = pixels * 3 / 4

        # Convert to twips (twentieths of a point).
        twips = points * 20

        # Add offset/padding.
        width = twips + 390

        return width
