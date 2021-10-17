import os.path
import tkinter as tk
from tkinter import ttk
from tkinter.filedialog import asksaveasfilename, askopenfilename, askdirectory, askopenfilenames

from pycicle.basetypes import FileBase, FolderBase, ChoiceBase
from pycicle.help_funcs import get_parser_help, get_argument_help
from pycicle.tools.document import short_line
from pycicle.tools.tktooltip import CreateToolTip
from pycicle.tools.utils import MISSING, TRUE, FALSE, redirect_output


def many_column_string(arg):
    if arg.many is True:
        return TRUE
    if arg.many is False:
        return FALSE
    return str(arg.many)  # in case of number


def _get_dialog(win, title, xy, wh=None):
    dialog = tk.Toplevel(win)
    dialog.title(title)
    if wh:
        dialog.geometry(f"{wh[0]}x{wh[1]}+{xy[0]}+{xy[1]}")
    else:
        dialog.geometry(f"+{xy[0]}+{xy[1]}")
    return dialog


def show_text_dialog(win, title, text, wh, xy):
    dialog = _get_dialog(win, title, wh=wh, xy=xy)
    dialog.config(bg="white")
    widget = tk.Text(dialog, bg="white", font=('Helvetica', 10, 'normal'))
    widget.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
    widget.insert(tk.END, text)
    widget.config(state=tk.DISABLED)


class Button(tk.Button):
    def __init__(self, *args, tooltip=None, **kwargs):
        super().__init__(*args, **kwargs)
        if tooltip:
            self.tooltip(tooltip)

    def tooltip(self, text):
        CreateToolTip(self, text)
        return self


class OutputDialog(tk.Toplevel):
    '''A general class for redirecting I/O to this Text widget.'''

    def __init__(self, master, title, xy, wh=None, fg='white', bg='black', font=('Helvetica', 9, 'bold')):
        super().__init__(master)
        self.title(title)
        if wh:
            self.geometry(f"{wh[0]}x{wh[1]}+{xy[0]}+{xy[1]}")
        else:
            self.geometry(f"+{xy[0]}+{xy[1]}")
        self.text_area = tk.Text(self, fg=fg, bg=bg, font=font)
        self.text_area.pack()

    def write(self, string):
        self.text_area.insert(tk.END, string)


class FittingText(tk.Text):
    def insert(self, *args, **kwargs):
        result = super().insert(*args, **kwargs)
        self.reset_height()
        return result

    def reset_height(self):
        height = self.tk.call((self._w, "count", "-update", "-displaylines", "1.0", "end"))
        self.configure(height=height)


class BaseFrame(tk.Frame):
    norm_font = ('Helvetica', 10, 'normal')
    bold_font = ('Helvetica', 10, 'bold')
    head_kwargs = {'font': bold_font, 'anchor': tk.W}
    cell_kwargs = {'font': norm_font}
    grid_kwargs = {'padx': 4, 'pady': 1, 'sticky': tk.W}

    def __init__(self, master=None, **kwargs):
        super().__init__(master)
        self.master = master
        self._init(**kwargs)  # before create_widgets
        self.create_widgets()

    def _init(self, **kwargs):
        """" override for initialization before widgets are created """
        pass

    def create_widgets(self):
        raise NotImplementedError


def show_multi_choice_dialog(win, title, chosen, xy, wh=None):
    dialog = _get_dialog(win, title, wh=wh, xy=xy)
    dialog.grab_set()
    chosen_vars = {choice: tk.BooleanVar(value=boolean) for choice, boolean in chosen.items()}

    def get_button(choice):
        return tk.Checkbutton(dialog, variable=chosen_vars[choice])

    def get_label(choice):
        return tk.Label(dialog, text=str(choice))

    for row, choice in enumerate(chosen):
        get_button(choice).grid(row=row, column=0, padx=(5, 0))
        get_label(choice).grid(row=row, column=1, sticky=tk.W)

    def on_ok():
        chosen.update({choice: var.get() for choice, var in chosen_vars.items()})
        dialog.destroy()

    ok_button = Button(dialog, text='OK', command=on_ok, width=6)
    ok_button.grid(row=len(chosen), column=1, padx=4, pady=5)
    dialog.wait_window()


class TkArgWrapper(object):
    """
    'translation' class between parser arguments and the gui; e.g. responsible for creating widgets for different types
    and argument configurations.
    """
    strings = {
        'name': lambda arg: '*' + arg.name if arg.required else arg.name,
        'type': lambda arg: arg.type.__name__,
        'many': lambda arg: many_column_string(arg),
    }

    def __init__(self, app, argument):
        self.app = app
        self.argument = argument
        self.variable = None
        self.factory = {bool: self._get_boolean_value_widget,
                        FileBase: self._get_file_value_widget,
                        FolderBase: self._get_folder_value_widget,
                        ChoiceBase: self._get_choice_value_widget}
        self.widget = None  # reference for validation update
        self.help_button = None
        self.error = None

    @property
    def kwargs(self):  # to edit the actual args
        return self.app.parser.kwargs

    def get_value(self):
        value = getattr(self.kwargs,
                        self.argument.name,
                        MISSING)
        string = self.argument.encode(value)
        if self.variable is None:
            self.variable = tk.StringVar()
        self.variable.set(string)

    def set_value(self, event=None):
        try:
            setattr(self.kwargs,
                    self.argument.name,
                    self.variable.get().strip())
        except Exception as error:  # to also catch TclError, ArgumentTypeError
            self.widget.config(highlightthickness=1,
                               highlightbackground="red",
                               highlightcolor="red")
            self.help_button.config(fg='red')
            self.error = str(error)
        else:
            # ttk widgets do not have 'highlightthickness', but comboboxes cannot accept invalid values
            if not isinstance(self.widget, ttk.Combobox):
                self.widget.config(highlightthickness=0)
            self.help_button.config(fg='black')
            self.error = None
        return self.error is None

    def del_value(self):
        delattr(self.kwargs,
                self.argument.name)
        self.get_value()

    def create_widget(self, master, name, **kwargs):
        if name == 'value':
            self.widget = self._get_value_widget(master, **kwargs)
            return self.widget
        if name == 'help':
            return self._get_help_widget(master, **kwargs)
        return tk.Label(master, text=self.strings[name](self.argument), **kwargs)

    def _get_help_widget(self, master, **kwargs):

        def show():
            w, h = (480, 360)
            x = self.help_button.winfo_rootx() + self.help_button.winfo_width() + 5
            y = self.help_button.winfo_rooty() - h - 30
            help_text = get_argument_help(self.argument, error=self.error, separator=short_line)
            show_text_dialog(self.app.master, title=f"help: {self.argument.name}",
                             text=help_text, wh=(w, h), xy=(x, y))

        self.help_button = Button(master, text='?', width=3, command=show, tooltip='more info', **kwargs)
        return self.help_button

    def _get_value_widget(self, master, **kwargs):
        # if self.argument.missing is not MISSING:
        #     return self._get_missing_widget(master, **kwargs)
        for cls, widget_getter in self.factory.items():
            if issubclass(self.argument.type, cls):
                return widget_getter(master, **kwargs)
        return self._get_string_value_widget(master, **kwargs)

    def _get_string_value_widget(self, master, **kwargs):
        self.get_value()
        widget = tk.Entry(master, textvariable=self.variable, **kwargs)
        widget.bind('<KeyRelease>', self.app.set_values)
        return widget

    def _open_file_dialog(self):
        filetypes = [('', '.' + ext) for ext in self.argument.type.extensions]
        if self.argument.many:  # append in case of many
            filenames = askopenfilenames(filetypes=filetypes)
            self.variable.set(f"{self.variable.get()}, {', '.join(filenames)}")
        else:
            filename = askopenfilename(filetypes=filetypes)
            self.variable.set(filename)
        self.app.set_values()

    def _open_folder_dialog(self):
        foldername = askdirectory(mustexist=self.argument.type.existing)
        if self.argument.many:  # append in case of many
            self.variable.set(f"{self.variable.get()}, {foldername}")
        else:
            self.variable.set(foldername)
        self.app.set_values()

    def _get_dialog_value_widget(self, master, command, **kwargs):
        widget = tk.Frame(master=master)

        entry_field = tk.Entry(widget, textvariable=self.variable, **kwargs)
        entry_field.bind('<KeyRelease>', self.app.set_values)
        entry_field.pack(side=tk.LEFT, fill=tk.X)

        file_button = Button(widget, text='...', command=command, width=2, tooltip='select a file')
        file_button.pack(side=tk.RIGHT, fill=tk.X, padx=(4, 0))
        return widget

    def _get_file_value_widget(self, master, **kwargs):
        self.get_value()
        return self._get_dialog_value_widget(master, command=self._open_file_dialog, **kwargs)

    def _get_folder_value_widget(self, master, **kwargs):
        self.get_value()
        return self._get_dialog_value_widget(master, command=self._open_folder_dialog, **kwargs)

    def _get_base_choice_value_widget(self, master, values, **kwargs):
        def on_select(event):
            self.variable.set(widget.get())
            self.app.set_values()

        if 'state' not in kwargs:
            kwargs['state'] = "readonly"
        self.get_value()
        default = self.argument.encode(self.argument.default)
        if default in values:
            values.remove(default)
            values.insert(0, default)
        else:
            values.insert(0, '')
        widget = ttk.Combobox(master, values=values)
        widget.config(textvariable=self.variable, **kwargs)
        widget.bind("<<ComboboxSelected>>", on_select)
        return widget

    def _get_choice_value_widget(self, master, **kwargs):
        if self.argument.many:
            return self._get_multi_choice_value_widget(master, **kwargs)

        values = list(self.argument.type.choices)
        return self._get_base_choice_value_widget(master, values=values, **kwargs)

    def _get_boolean_value_widget(self, master, **kwargs):
        if self.argument.many:
            return self._get_multi_choice_value_widget(master, **kwargs)
        return self._get_base_choice_value_widget(master, values=[FALSE, TRUE], **kwargs)

    def _get_multi_choice_value_widget(self, master, **kwargs):
        self.get_value()
        choices = list(self.argument.type.choices)
        chosen_values = set(c.strip() for c in self.variable.get().split(' '))
        chosen = {choice: (choice in chosen_values) for choice in choices}

        def show():
            x = self.app.winfo_rootx() + self.app.winfo_width() + 5
            y = self.app.winfo_rooty() - 90
            show_multi_choice_dialog(self.app.master, title=f"{self.argument.name}",
                                     chosen=chosen, xy=(x, y))
            self.variable.set(' '.join(choice for choice, boolean in chosen.items() if boolean))
            self.app.set_values()

        return self._get_dialog_value_widget(master=master, command=show, **kwargs)


# ==================================================================

class CommandFrame(BaseFrame):
    def _init(self, **kwargs):
        self.selected = {'short': False, 'path': False, 'list': False}
        self.kwargs = {'short': {'text': '><',
                                 'tooltip': 'short: select to see command line with short flags (like -f)'},
                       'path': {'text': '\\..\\',
                                'tooltip': 'path: select to see command line with full path to python script'},
                       'list': {'text': '[..]',
                                'tooltip': 'list: show the commands on the command line as a list'}}
        self.buttons = {}

    def create_widgets(self):
        def switch(name):
            def inner():
                selected = self.selected[name] = not self.selected[name]
                self.buttons[name].config(relief=tk.SUNKEN if selected else tk.RAISED)
                self.show_command()

            return inner

        def get_button(name):
            return Button(self, command=switch(name), font=self.norm_font, **self.kwargs[name])

        for name in self.selected:
            self.buttons[name] = get_button(name)
            self.buttons[name].pack(side=tk.LEFT)

        self.view = FittingText(self, width=72, height=1, font=self.norm_font)
        self.view.pack(side=tk.LEFT, fill=tk.X, padx=5)

    def show_command(self):
        cmd = self.master.get_command(**self.selected)
        self.view.config(state=tk.NORMAL)
        self.view.delete(1.0, tk.END)
        if cmd is not None:
            self.view.insert(1.0, cmd)
        self.view.config(state=tk.DISABLED)


class FormFrame(BaseFrame):
    column_names = ('name', 'value', 'type', 'many', 'help')

    column_grid_kwargs = {'name': {'sticky': tk.E},  # overrides grid_kwargs
                          'value': {'sticky': tk.EW},
                          'many': {'sticky': None}}
    column_cell_kwargs = {'value': {'width': 48}}

    def _init(self):
        self.wrappers = [TkArgWrapper(app=self.master,
                                      argument=arg)
                         for arg in self.master.arguments]
        self.short = True  # switched before first use

    def _get_grid_kwargs(self, col_name):
        grid_kwargs = self.grid_kwargs.copy()
        grid_kwargs.update(self.column_grid_kwargs.get(col_name, {}))
        return grid_kwargs

    def _get_cell_kwargs(self, col_name):
        cell_kwargs = self.cell_kwargs.copy()
        cell_kwargs.update(self.column_cell_kwargs.get(col_name, {}))
        return cell_kwargs

    def destroy(self):
        del self.wrappers[:]
        super().destroy()

    def create_widgets(self):
        for i, col_name in enumerate(self.column_names):
            self._create_widget(col_name).grid(row=0, column=i,
                                               **self._get_grid_kwargs(col_name))
        for i, wrapper in enumerate(self.wrappers):
            for j, col_name in enumerate(self.column_names):
                self._create_widget(col_name, wrapper).grid(row=i + 1, column=j,
                                                            **self._get_grid_kwargs(col_name))

    def _create_widget(self, col_name, wrapper=None):
        if wrapper is None:  # title row:
            return tk.Label(self, text=col_name, **self.head_kwargs)
        return wrapper.create_widget(self, name=col_name, **self._get_cell_kwargs(col_name))


class ButtonBar(BaseFrame):
    button_configs = dict(
        run={'tooltip': 'run the script with these command line arguments'},
        save={'tooltip': 'save the command line to the same file'},
        save_as={'tooltip': 'save the command line to file'},
        load={'tooltip': 'load the command line from file'},
        reset={'tooltip': 'reset all values to default or empty'},
        help={'text': '?', 'width': 3, 'tooltip': 'docs on this program and its use'}
    )

    grid_kwargs = {'padx': 2, 'pady': 2}
    button_kwargs = {'width': 6, 'font': ('Helvetica', 10, 'normal')}

    def create_widgets(self):
        self.buttons = []
        for name, config in self.button_configs.items():
            self.buttons.append(self.get_button(name, config))
        self.config(padx=5, pady=5)

    def get_button(self, name, config):
        config = config.copy()
        kwargs = self.button_kwargs.copy()
        kwargs.update(command=getattr(self.master, name))
        kwargs.update(text=config.pop(name, name.replace('_', ' ')))
        kwargs.update(**config)
        button = Button(master=self, **kwargs)
        button.grid(row=0, column=len(self.buttons), **self.grid_kwargs)
        return button


class ArgGui(BaseFrame):
    icon_file = os.path.abspath(os.path.join(os.path.dirname(__file__), 'images/icon.png'))

    def __init__(self, parser, target):
        super().__init__(tk.Tk(), parser=parser, target=target)
        self.master.eval('tk::PlaceWindow . center')
        self.master.after(100, self.command_frame.show_command)

    def _init(self, parser, target):
        self.parser = parser
        self.target = target
        self.filename = None
        self.master.title(f"PyCicle: {type(parser).__name__}")
        icon = tk.PhotoImage(file=self.icon_file)
        self.master.iconphoto(False, icon)
        self.grid(row=0, column=0, padx=10, pady=5)
        self.run_dialog = None

    @property
    def arguments(self):
        return self.parser.arguments.values()

    def create_widgets(self):
        self.form = FormFrame(self)
        self.command_frame = CommandFrame(self)
        self.button_bar = ButtonBar(self)
        self.form.grid(row=0, column=0, padx=2, pady=2)
        self.command_frame.grid(row=1, column=0, padx=2, pady=8)
        self.button_bar.grid(row=2, column=0, padx=2, pady=2)

    def create_run_window(self):
        self.run_dialog = OutputDialog(self.master, title='output', xy=(400, 400))
        return self.run_dialog

    def set_values(self, event=None):
        success = True
        for wrapper in self.form.wrappers:
            success &= wrapper.set_value()
        self.command_frame.show_command()
        return success

    def get_values(self):
        for wrapper in self.form.wrappers:
            wrapper.get_value()
        self.command_frame.show_command()

    def get_command(self, short=False, path=False, list=False):
        cmd_line = self.parser.command(short=short, prog=True, path=path)
        if list:
            return str(cmd_line.split())
        return cmd_line

    def run(self):
        if self.target is None:
            tk.messagebox.showinfo('nothing to run', 'no runnable target was configured for this app')
        elif self.set_values():
            dialog = self.create_run_window()
            with redirect_output(dialog):
                print('running: ', self.get_command(), '\n')
                self.parser(self.target)

    def save(self):
        if self.set_values():
            if not self.filename:
                self.save_as()
            else:
                self.parser.save(self.filename)

    def save_as(self):
        if self.set_values():
            self.filename = asksaveasfilename(defaultextension=".cl")
            if self.filename:
                self.parser.save(self.filename)

    def load(self):
        filename = askopenfilename(defaultextension=".cl")
        if filename:
            self.filename = filename
            try:
                self.parser = self.parser.load(self.filename)
            except Exception as e:
                tk.messagebox.showerror("error while loading file",
                                        f"message: {str(e)}\n\nprobable cause:\n"
                                        f"file is incompatible with the configuration of the parser")
            else:
                self.get_values()

    def reset(self):
        for wrapper in self.form.wrappers:
            wrapper.del_value()
        self.get_values()

    def help(self):
        help_text = get_parser_help(self.parser)
        x = self.winfo_rootx() + self.winfo_width() + 20
        y = self.winfo_rooty() - 36
        show_text_dialog(self.master, 'help', help_text, wh=(640, 640), xy=(x, y))
