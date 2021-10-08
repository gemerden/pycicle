import os.path
import tkinter as tk
from tkinter import ttk
from tkinter.filedialog import asksaveasfilename, askopenfilename, askdirectory, askopenfilenames

from pycicle.basetypes import FileBase, FolderBase, ChoiceBase
from pycicle.document import short_line
from pycicle.help_tools import get_parser_help, get_argument_help
from pycicle.tools import MISSING


def many_column_string(arg):
    if arg.many is True:
        return 'yes'
    if arg.many is False:
        return 'no'
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

    ok_button = tk.Button(dialog, text='OK', command=on_ok, width=6)
    ok_button.grid(row=len(chosen), column=1, padx=4, pady=5)
    dialog.wait_window()


class FittingText(tk.Text):
    def insert(self, *args, **kwargs):
        result = super().insert(*args, **kwargs)
        self.reset_height()
        return result

    def reset_height(self):
        height = self.tk.call((self._w, "count", "-update", "-displaylines", "1.0", "end"))
        self.configure(height=height)


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

    def get_value(self):
        value = getattr(self.app.parser,
                        self.argument.name)
        result = self.argument.encode(value)
        if self.argument.many is not False:  # many can be bool or int
            return ', '.join(result)
        return result

    def sync_value(self, event=None):
        if self.argument.novalue is not MISSING:
            if self.variable.get():
                value = self.argument.novalue
            else:
                value = self.argument.default
        else:
            value = self.variable.get().strip(', ')
            if self.argument.many is not False:
                value = [v.strip() for v in value.split(',') if v.strip()]

        try:
            setattr(self.app.parser, self.argument.name, value)
        except Exception as e:  # to also catch TclError, ArgumentTypeError
            self.widget.config(highlightthickness=1,
                               highlightbackground="red",
                               highlightcolor="red")
            self.help_button.config(fg='red')
            self.error = str(e)
            return False
        else:
            # ttk widgets do not have 'highlightthickness', but comboboxes cannot accept invalid values
            if not isinstance(self.widget, ttk.Combobox):
                self.widget.config(highlightthickness=0)
            self.help_button.config(fg='black')
            self.error = None
            return True

    def reset_value(self):
        delattr(self.app.parser,
                self.argument.name)
        if self.argument.novalue is not MISSING:
            self.variable.set(False)
        else:
            self.variable.set(self.get_value())

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

        self.help_button = tk.Button(master, text='?', width=3, command=show, **kwargs)
        return self.help_button

    def _get_value_widget(self, master, **kwargs):
        if self.argument.novalue is not MISSING:
            return self._get_novalue_widget(master, **kwargs)
        for cls, widget_getter in self.factory.items():
            if issubclass(self.argument.type, cls):
                return widget_getter(master, **kwargs)
        return self._get_string_value_widget(master, **kwargs)

    def _get_string_value_widget(self, master, **kwargs):
        self.variable = tk.StringVar(value=self.get_value())
        widget = tk.Entry(master, textvariable=self.variable, **kwargs)
        widget.bind('<KeyRelease>', self.app.synchronize)
        return widget

    def _open_file_dialog(self):
        filetypes = [('', '.' + ext) for ext in self.argument.type.extensions]
        if self.argument.many is not False:  # append in case of many
            filenames = askopenfilenames(filetypes=filetypes)
            self.variable.set(f"{self.variable.get()}, {', '.join(filenames)}")
        else:
            filename = askopenfilename(filetypes=filetypes)
            self.variable.set(filename)
        self.app.synchronize()

    def _open_folder_dialog(self):
        foldername = askdirectory(mustexist=self.argument.type.existing)
        if self.argument.many is not False:  # append in case of many
            self.variable.set(f"{self.variable.get()}, {foldername}")
        else:
            self.variable.set(foldername)
        self.app.synchronize()

    def _get_novalue_widget(self, master, **kwargs):
        self.variable = tk.BooleanVar(value=False)
        widget = tk.Frame(master)
        field = tk.Text(widget, height=1, **kwargs)
        field.pack(side=tk.LEFT, fill=tk.X)
        label = tk.Label(widget, text='include:')
        label.pack(side=tk.LEFT)

        def sync(sync_all=True):
            if sync_all:
                self.app.synchronize()
            field.config(state=tk.NORMAL)
            field.delete('1.0', tk.END)
            field.insert(tk.END, self.get_value())
            field.config(state=tk.DISABLED)

        sync(sync_all=False)
        check = tk.Checkbutton(widget, variable=self.variable, command=sync)
        check.pack(side=tk.RIGHT, padx=(4, 0))
        return widget

    def _get_dialog_value_widget(self, master, command, **kwargs):
        widget = tk.Frame(master=master)

        entry_field = tk.Entry(widget, textvariable=self.variable, **kwargs)
        entry_field.bind('<KeyRelease>', self.app.synchronize)
        entry_field.pack(side=tk.LEFT, fill=tk.X)

        file_button = tk.Button(widget, text='...', command=command, width=2)
        file_button.pack(side=tk.RIGHT, fill=tk.X, padx=(4, 0))
        return widget

    def _get_file_value_widget(self, master, **kwargs):
        self.variable = tk.StringVar(value=self.get_value())
        return self._get_dialog_value_widget(master, command=self._open_file_dialog, **kwargs)

    def _get_folder_value_widget(self, master, **kwargs):
        self.variable = tk.StringVar(value=self.get_value())
        return self._get_dialog_value_widget(master, command=self._open_folder_dialog, **kwargs)

    def _get_base_choice_value_widget(self, master, values, **kwargs):
        def on_select(event):
            self.variable.set(widget.get())
            self.app.synchronize()

        if 'state' not in kwargs:
            kwargs['state'] = "readonly"
        self.variable = tk.StringVar(value=self.get_value())
        start_values = [] if self.argument.required else ['']
        widget = ttk.Combobox(master, values=start_values + values)
        widget.config(textvariable=self.variable, **kwargs)
        widget.bind("<<ComboboxSelected>>", on_select)
        return widget

    def _get_choice_value_widget(self, master, **kwargs):
        if self.argument.many is not False:
            return self._get_multi_choice_value_widget(master, **kwargs)

        values = list(self.argument.type.choices)
        return self._get_base_choice_value_widget(master, values=values, **kwargs)

    def _get_boolean_value_widget(self, master, **kwargs):
        if self.argument.many is not False:
            return self._get_multi_choice_value_widget(master, **kwargs)
        return self._get_base_choice_value_widget(master, values=['no', 'yes'], **kwargs)

    def _get_multi_choice_value_widget(self, master, **kwargs):
        self.variable = tk.StringVar(value=self.get_value())
        choices = list(self.argument.type.choices)
        chosen_values = set(c.strip() for c in self.variable.get().split(','))
        chosen = {choice: (choice in chosen_values) for choice in choices}

        def show():
            x = self.app.winfo_rootx() + self.app.winfo_width() + 5
            y = self.app.winfo_rooty() - 90
            show_multi_choice_dialog(self.app.master, title=f"{self.argument.name}",
                                     chosen=chosen, xy=(x, y))
            self.variable.set(', '.join(choice for choice, boolean in chosen.items() if boolean))
            self.app.synchronize()

        return self._get_dialog_value_widget(master=master, command=show, **kwargs)


# ==================================================================

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
        self.command_string_var = tk.StringVar()
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
        self._create_command_bar()

    def _create_widget(self, col_name, wrapper=None):
        if wrapper is None:  # title row:
            return tk.Label(self, text=col_name, **self.head_kwargs)
        return wrapper.create_widget(self, name=col_name, **self._get_cell_kwargs(col_name))

    def _create_command_bar(self):
        self.cmd_button = tk.Button(self, text='-/--', command=self.switch_command, font=self.bold_font)
        self.cmd_button.grid(row=len(self.wrappers) + 1, column=0)

        self.cmd_view = FittingText(self, width=64, height=1, font=self.norm_font)
        self.cmd_view.grid(row=len(self.wrappers) + 1, column=1, columnspan=3, sticky=tk.EW)

    def switch_command(self):
        self.short = not self.short
        if not self.master.synchronize():
            self.short = not self.short

    def show_command(self, ok=True):
        cmd = self.master.command(self.short)
        self.cmd_view.config(state=tk.NORMAL)
        self.cmd_view.delete(1.0, tk.END)
        if ok:
            self.cmd_view.insert(1.0, cmd)
        self.cmd_view.config(state=tk.DISABLED)


class ButtonBar(BaseFrame):
    button_configs = dict(
        run=None,
        save=None,
        save_as=None,
        load=None,
        reset=None,
        help={'text': '?', 'width': 3}
    )

    grid_kwargs = {'padx': 2, 'pady': 2}
    button_kwargs = {'width': 6, 'font': ('Helvetica', 10, 'normal')}

    def create_widgets(self):
        self.buttons = []
        for name, config in self.button_configs.items():
            self.buttons.append(self.get_button(name, config))
        self.config(padx=5, pady=5)

    def get_button(self, name, config):
        kwargs = self.button_kwargs.copy()
        kwargs.update(command=getattr(self.master, name))
        kwargs.update(config or {'text': name.replace('_', ' ')})
        button = tk.Button(master=self, **kwargs)
        button.grid(row=0, column=len(self.buttons), **self.grid_kwargs)
        return button


class ArgGui(BaseFrame):
    icon_file = os.path.abspath(os.path.join(os.path.dirname(__file__), 'images/icon.png'))

    def __init__(self, parser, target):
        super().__init__(tk.Tk(), parser=parser, target=target)
        self.master.eval('tk::PlaceWindow . center')
        self.synchronize()

    def _init(self, parser, target):
        self.parser = parser
        self.target = target
        self.filename = None
        self.master.title(f"PyCicle: {type(parser).__name__}")
        icon = tk.PhotoImage(file=self.icon_file)
        self.master.iconphoto(False, icon)
        self.grid(row=0, column=0, padx=10, pady=5)

    @property
    def arguments(self):
        return self.parser._arguments

    def create_widgets(self):
        self.form = FormFrame(self)
        self.button_bar = ButtonBar(self)
        self.form.grid(row=0, column=0, padx=2, pady=2)
        self.button_bar.grid(row=2, column=0, padx=2, pady=2)

    def synchronize(self, event=None):
        success = True
        for wrapper in self.form.wrappers:
            success &= wrapper.sync_value()
        self.form.show_command(ok=success)
        return success

    def command(self, short):
        return self.parser._command(short, prog=True)

    def run(self):
        if self.target is None:
            tk.messagebox.showinfo('nothing to run', 'no runnable target was configured for this app')
        if self.synchronize():
            try:
                self.parser(self.target)
            except Exception as e:
                tk.messagebox.showerror("error", str(e))

    def save(self):
        if self.synchronize():
            if not self.filename:
                self.save_as()
            else:
                self.parser._save(self.filename)

    def save_as(self):
        if self.synchronize():
            self.filename = asksaveasfilename(defaultextension=".json")
            if self.filename:
                self.parser._save(self.filename)

    def load(self):
        filename = askopenfilename(defaultextension=".json")
        if filename:
            self.filename = filename
            try:
                self.parser = self.parser._load(self.filename)
            except Exception as e:
                tk.messagebox.showerror("error while loading file",
                                     f"message: {str(e)}\n\nprobable cause:\n"
                                     f"file is incompatible with the configuration of the parser")
            else:
                self.form.destroy()
                self.form = FormFrame(self)
                self.form.grid(row=0, column=0)

    def reset(self):
        for wrapper in self.form.wrappers:
            wrapper.reset_value()
        self.synchronize()

    def help(self):
        help_text = get_parser_help(self.parser)
        x = self.winfo_rootx() + self.winfo_width() + 20
        y = self.winfo_rooty() - 36
        show_text_dialog(self.master, 'help', help_text, wh=(640, 640), xy=(x, y))
