import os.path
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.filedialog import asksaveasfilename, askopenfilename, askdirectory, askopenfilenames

from basetypes import FileBase, FolderBase, ChoiceBase


def many_string(arg):
    if arg.many is True:
        return 'yes'
    if arg.many is False:
        return 'no'
    return str(arg.many)


class TkArgWrapper(object):
    strings = {
        'name': lambda self, arg: '*' + arg.name if arg.required else arg.name + ':',
        'value': lambda self, arg: str(self.get_value()),
        'type': lambda self, arg: arg.type.__name__,
        'many': lambda self, arg: many_string(arg),
        'help': lambda self, arg: arg.help,
    }

    def __init__(self, app, argument):
        self.app = app
        self.argument = argument
        self.var = None
        self.factory = {bool: self._get_boolean_value_widget,
                        FileBase: self._get_file_value_widget,
                        FolderBase: self._get_folder_value_widget,
                        ChoiceBase: self._get_choice_value_widget}
        self.widget = None  # reference for validation update

    def get_value(self):
        try:
            value = getattr(self.app.parser,
                            self.argument.name)
        except AttributeError:
            value = self.argument.default or None
        if self.argument.type is bool:  # special case, hard to do otherwise
            value = bool(value)
        elif self.argument.type not in self.factory:
            value = self.argument.encode(value)
        return value

    def sync_value(self, event=None):
        value = self.var.get()
        try:
            if self.argument.many is not False:
                value = [v.strip() for v in value.strip(',').split(',') if v.strip()]
            setattr(self.app.parser, self.argument.name, value)
        except Exception as e:  # to also catch TclError, ArgumentTypeError
            self.widget.config(highlightthickness=1,
                               highlightbackground="red",
                               highlightcolor="red")
            return False
        else:
            # ttk widgets do not have 'highlightthickness', but cannot accept invalid values
            if not isinstance(self.widget, ttk.Combobox):
                self.widget.config(highlightthickness=0)
            return True

    def reset_value(self):
        delattr(self.app.parser,
                self.argument.name)
        self.var.set(self.get_value())

    def create_widget(self, master, name, **kwargs):
        if name == 'value':
            if self.argument.constant:
                kwargs['state'] = tk.DISABLED
            self.widget = self._get_value_widget(master, **kwargs)
            return self.widget
        if name == 'help':
            return self._get_help_widget(master, **kwargs)
        return tk.Label(master, text=self._get_string(name), **kwargs)

    def _get_help_widget(self, master, **kwargs):
        if not self.argument.help:
            return tk.Label(master)

        def show():
            w, h = (320, 120)
            x = button.winfo_rootx() + button.winfo_width() + 5
            y = button.winfo_rooty() - h - 30
            show_text_dialog(self.app.master, title='help', text=self.argument.help, wh=(w, h), xy=(x, y))

        button = tk.Button(master, text='?', width=3, command=show, **kwargs)
        return button

    def _get_widget_getter(self):
        for cls, widget_getter in self.factory.items():
            if issubclass(self.argument.type, cls):
                return widget_getter
        return self._get_string_value_widget

    def _get_string(self, name):
        try:
            return self.strings[name](self, self.argument)
        except KeyError:
            raise AttributeError(f"no string for column '{name}'")

    def _get_value_widget(self, master, **kwargs):
        create_widget = self._get_widget_getter()
        return create_widget(master, **kwargs)

    def _get_string_value_widget(self, master, **kwargs):
        self.var = tk.StringVar(value=self.get_value())
        widget = tk.Entry(master, textvariable=self.var, **kwargs)
        widget.bind('<KeyRelease>', self.app.synchronize)
        return widget

    def _get_boolean_value_widget(self, master, **kwargs):
        self.var = tk.BooleanVar(value=self.get_value())
        kwargs.update(variable=self.var, command=self.app.synchronize, anchor=tk.W)
        return tk.Checkbutton(master, **kwargs)

    def _open_file_dialog(self):
        if self.argument.many is not False:
            filename_s = askopenfilenames(filetypes=['*.' + ext for ext in self.argument.type.extensions])
        else:
            filename_s = askopenfilename(filetypes=['*.' + ext for ext in self.argument.type.extensions])
        self.var.set(filename_s)
        self.app.synchronize()

    def _open_folder_dialog(self):
        self.var.set(askdirectory(mustexist=self.argument.type.exists))
        self.app.synchronize()

    def _get_file_folder_value_widget(self, master, command, **kwargs):
        self.var = tk.StringVar(value=self.get_value())
        widget = tk.Frame(master=master)

        entry_field = tk.Entry(widget, textvariable=self.var, **kwargs)
        entry_field.bind('<KeyRelease>', self.app.synchronize)
        entry_field.pack(side=tk.LEFT, fill=tk.X)

        file_button = tk.Button(widget, text='...', command=command, height=1, width=3)
        file_button.pack(side=tk.RIGHT, fill=tk.X)
        return widget

    def _get_file_value_widget(self, master, **kwargs):
        return self._get_file_folder_value_widget(master, command=self._open_file_dialog, **kwargs)

    def _get_folder_value_widget(self, master, **kwargs):
        return self._get_file_folder_value_widget(master, command=self._open_folder_dialog, **kwargs)

    def _get_choice_value_widget(self, master, **kwargs):
        if self.argument.many is not False:
            return self._get_string_value_widget(master, **kwargs)

        def on_select(event):
            self.var.set(widget.get())
            self.app.synchronize()

        if 'state' not in kwargs:
            kwargs['state'] = "readonly"
        self.var = tk.StringVar(value=self.get_value())
        values = [] if self.argument.required else ['']
        values.extend(map(str, self.argument.type.choices))
        widget = ttk.Combobox(master, values=values)
        widget.config(textvariable=self.var, **kwargs)
        widget.bind("<<ComboboxSelected>>", on_select)
        return widget


# ==================================================================

class BaseFrame(tk.Frame):
    norm_font = ('Helvetica', 10, 'normal')
    bold_font = ('Helvetica', 10, 'bold')
    head_kwargs = {'font': bold_font, 'anchor': tk.W}
    cell_kwargs = {'font': norm_font}
    grid_kwargs = {'padx': 4, 'pady': 1, 'sticky': tk.W}

    def __init__(self, master=None, **kwargs):
        super().__init__(master)
        self.master = master
        self._init(**kwargs)  # before create widgets
        self.create_widgets()

    def _init(self, **kwargs):
        """" initialization before widgets are created """
        pass

    def create_widgets(self):
        raise NotImplementedError


class FormFrame(BaseFrame):
    col_names = ('name', 'value', 'type', 'many', 'help')

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
        for i, col_name in enumerate(self.col_names):
            self._create_widget(col_name).grid(row=0, column=i,
                                               **self._get_grid_kwargs(col_name))
        for i, wrapper in enumerate(self.wrappers):
            for j, col_name in enumerate(self.col_names):
                self._create_widget(col_name, wrapper).grid(row=i + 1, column=j,
                                                            **self._get_grid_kwargs(col_name))
        self._create_command_bar()

    def _create_widget(self, col_name, wrapper=None):
        if wrapper is None:  # title row:
            return tk.Label(self, text=col_name, **self.head_kwargs)
        return wrapper.create_widget(self, name=col_name, **self._get_cell_kwargs(col_name))

    def _create_command_bar(self):
        self.cmd_button = tk.Button(self, text='-/--', command=self.switch_command, font=self.bold_font)
        self.cmd_button.grid(row=len(self.wrappers) + 1, column=0, padx=2, pady=4)

        self.cmd_view = tk.Text(self, width=64, height=1, font=self.norm_font)
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
    butt_kwargs = {'width': 6, 'font': ('Helvetica', 10, 'normal')}

    def create_widgets(self):
        self.buttons = []
        for name, config in self.button_configs.items():
            self.buttons.append(self.get_button(name, config))
        self.config(padx=5, pady=5)

    def get_button(self, name, config):
        kwargs = self.butt_kwargs.copy()
        kwargs.update(command=getattr(self.master, name))
        kwargs.update(config or {'text': name.replace('_', ' ')})
        button = tk.Button(master=self, **kwargs)
        button.grid(row=0, column=len(self.buttons), **self.grid_kwargs)
        return button


class App(BaseFrame):
    icon_file = os.path.abspath(os.path.join(os.path.dirname(__file__), 'images/icon.png'))

    def __init__(self, parser):
        super().__init__(tk.Tk(), parser=parser)
        self.master.eval('tk::PlaceWindow . center')

    def _init(self, parser):
        self.parser = parser
        self.filename = None
        self.master.title('ClaPy')
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
        return self.parser._command(short)

    def run(self):
        if self.synchronize():
            if self.parser._runnable():
                self.parser._call()
            else:
                messagebox.showerror('nothing to run', 'no _runnable was configured for this app')

    def save(self):
        if self.synchronize():
            if not self.filename:
                self.save_as()
            else:
                self.parser._save(self.filename)

    def save_as(self):
        if self.synchronize():
            self.filename = asksaveasfilename(defaultextension=".json")
            self.parser._save(self.filename)

    def load(self):
        self.filename = askopenfilename(defaultextension=".json")
        try:
            self.parser = self.parser._load(self.filename)
        except Exception as e:
            messagebox.showerror("error loading file", f"message: {str(e)}\n\nprobable cause:\n"
                                                       f"file is incompatible with the configuration of the parser")
        else:
            self.form.destroy()
            self.form = FormFrame(self)
            self.form.grid(row=0, column=0)

    def reset(self):
        for wrapper in self.form.wrappers:
            wrapper.reset_value()

    def help(self):
        help_text = type(self.parser).__doc__ or ""
        x = self.winfo_rootx() + self.winfo_width() + 20
        y = self.winfo_rooty() - 36
        show_text_dialog(self.master, 'help', help_text, wh=(640, 640), xy=(x, y))


def show_text_dialog(win, title, text, wh, xy):
    dialog = tk.Toplevel(win)
    dialog.title(title)
    dialog.geometry(f"{wh[0]}x{wh[1]}+{xy[0]}+{xy[1]}")
    dialog.config(bg="white")
    widget = tk.Text(dialog, bg="white", font=('Helvetica', 10, 'normal'))
    widget.pack(expand=True, fill=tk.BOTH)
    widget.insert(tk.END, text)
    widget.config(state=tk.DISABLED)
