import os.path
import tkinter as tk
from tkinter import messagebox
from tkinter.filedialog import asksaveasfilename, askopenfilename


class TkArgWrapper(object):
    strings = {
        'name': lambda self, arg: '*' + arg.name if arg.required else arg.name,
        'value': lambda self, arg: str(self.get_value()),
        'type': lambda self, arg: arg.type.__name__,
        'many': lambda self, arg: str(arg.many).lower(),
        'help': lambda self, arg: arg.help,
    }

    def __init__(self, app, argument):
        self.argument = argument
        self.app = app
        self.var = None
        self.factory = {str: self._get_string_value_widget,
                        int: self._get_string_value_widget,
                        float: self._get_string_value_widget,
                        bool: self._get_boolean_value_widget}
        self.widget = None  # reference for validation update

    def get_value(self):
        try:
            return self.app.namespace[self.argument.name]
        except KeyError:
            return self.argument.default or self.argument.type()

    def sync_value(self, event=None):
        try:
            value = self.var.get()
            if self.argument.many is not False:
                value = [v.strip() for v in value.strip(',').split(',') if v.strip()]
            value = self.argument.validate(value)
        except Exception as e:  # to also catch TclError
            self.widget.config(highlightthickness=1,
                               highlightbackground="red",
                               highlightcolor="red")
            return False
        else:
            self.widget.config(highlightthickness=0)
            self.app.namespace[self.argument.name] = value
            return True

    def create_widget(self, master, col_name, **kwargs):
        if col_name == 'value':
            if self.argument.constant:
                kwargs['state'] = tk.DISABLED
            return self._get_value_widget(master, **kwargs)
        if col_name == 'many':
            return self._get_bool_widget(master, **kwargs)
        return tk.Label(master, text=self._get_string(col_name), **kwargs)

    def _get_string(self, col_name):
        try:
            return self.strings[col_name](self, self.argument)
        except KeyError:
            raise AttributeError(f"no string for column '{col_name}'")

    def _get_value_widget(self, master, **kwargs):
        return self.factory[self.argument.type](master, **kwargs)

    def _get_bool_widget(self, master, **kwargs):
        button = tk.Checkbutton(master, state=tk.DISABLED, **kwargs)
        if self.argument.many is not False:
            button.select()
        return button

    def _get_string_value_widget(self, master, **kwargs):
        self.var = tk.StringVar(value=self.get_value())
        self.widget = tk.Entry(master, textvariable=self.var, **kwargs)
        self.widget.bind('<KeyRelease>', self.sync_value)
        return self.widget

    def _get_boolean_value_widget(self, master, **kwargs):
        self.var = tk.BooleanVar(value=self.get_value())
        kwargs.update(variable=self.var, command=self.sync_value)
        self.widget = tk.Checkbutton(master, **kwargs)
        return self.widget


# ==================================================================

class BaseFrame(tk.Frame):
    norm_font = ('Helvetica', 10, 'normal')
    bold_font = ('Helvetica', 10, 'bold')
    head_kwargs = {'font': bold_font}
    cell_kwargs = {'font': norm_font}
    grid_kwargs = {'padx': 2, 'pady': 1, 'sticky': tk.W}

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

    column_kwargs = {'name': {'sticky': tk.E},  # overrides grid_kwargs
                     'many': {'sticky': None}}

    def _init(self):
        self.wrappers = {arg.name: TkArgWrapper(app=self.master,
                                                argument=arg)
                         for arg in self.arguments}
        self.command_string_var = tk.StringVar()

    @property
    def arguments(self):
        return self.master.arguments

    def _get_col_kwargs(self, col_name):
        col_kwargs = self.grid_kwargs.copy()
        col_kwargs.update(self.column_kwargs.get(col_name, {}))
        return col_kwargs

    def destroy(self):
        self.wrappers.clear()
        super().destroy()

    def create_widgets(self):
        for i, col_name in enumerate(self.col_names):
            self._create_widget(col_name).grid(row=0, column=i,
                                               **self._get_col_kwargs(col_name))
        for i, arg in enumerate(self.arguments):
            for j, col_name in enumerate(self.col_names):
                self._create_widget(col_name, arg).grid(row=i + 1, column=j,
                                                        **self._get_col_kwargs(col_name))
        self._create_command_bar()

    def _create_widget(self, col_name, argument=None):
        if argument is None:  # title row:
            return tk.Label(self, text=col_name, **self.head_kwargs)
        return self.wrappers[argument.name].create_widget(master=self, col_name=col_name, **self.cell_kwargs)

    def _create_command_bar(self):
        cmd_button = tk.Button(self, text='cmd', command=self.show, font=self.bold_font)
        cmd_view = tk.Entry(self, textvariable=self.command_string_var, font=self.norm_font)
        cmd_button.grid(row=len(self.wrappers) + 1, column=0, padx=2, pady=4)
        cmd_view.grid(row=len(self.wrappers) + 1, column=1, columnspan=4,
                      padx=2, pady=2, sticky=tk.E + tk.W + tk.N + tk.S)

    def show(self):
        if self.master.synchronize():
            self.command_string_var.set(self.master.parser.command(True))


class ButtonBar(BaseFrame):
    button_names = ('run', 'save', 'save_as', 'load')

    button_kwargs = {'width': 6, 'font': ('Helvetica', 10, 'normal')}
    grid_kwargs = {'padx': 2, 'pady': 2}

    def _init(self):
        self.buttons = {}

    def create_widgets(self):
        for name in self.button_names:
            self.buttons[name] = self.get_button(name)
        self.config(padx=5, pady=5)

    def get_button(self, name):
        button = tk.Button(self, text=name.replace('_', ' '),
                           command=getattr(self.master, name),
                           **self.button_kwargs)
        button.grid(row=0, column=len(self.buttons), **self.grid_kwargs)
        return button


class App(BaseFrame):
    icon_file = os.path.abspath(os.path.join(os.path.dirname(__file__), 'images/icon.png'))

    def __init__(self, parser):
        super().__init__(master=tk.Tk(), parser=parser)

    def _init(self, parser):
        self.parser = parser
        self.arguments = tuple(parser.__arguments__())
        self.filename = None
        self.set_visuals(name='ClaPy',
                         icon=self.icon_file)

    @property
    def namespace(self):
        return self.parser.namespace

    def set_visuals(self, name, icon):
        self.master.title(name)
        icon = tk.PhotoImage(file=icon)
        self.master.iconphoto(False, icon)
        self.grid(row=0, column=0, padx=10, pady=5)

    def create_widgets(self):
        self.form = FormFrame(self)
        self.button_bar = ButtonBar(self)
        self.form.grid(row=0, column=0, padx=2, pady=2)
        self.button_bar.grid(row=2, column=0, padx=2, pady=2)

    def synchronize(self):
        success = True
        for wrapper in self.form.wrappers.values():
            success &= wrapper.sync_value()
        return success

    def run(self):
        if self.synchronize():
            self.parser.call()

    def save(self):
        if self.synchronize():
            if not self.filename:
                self.save_as()
            else:
                self.parser.save(self.filename)

    def save_as(self):
        if self.synchronize():
            self.filename = asksaveasfilename(defaultextension=".json")
            self.parser.save(self.filename)

    def load(self):
        self.filename = askopenfilename(defaultextension=".json")
        try:
            self.parser = self.parser.load(self.filename)
        except Exception as e:
            messagebox.showerror("error loading file", f"message: {str(e)}\n\nprobable cause: "
                                                       f"file is incompatible with the configuration of the parser")
        else:
            self.arguments = tuple(self.parser.__arguments__())
            self.form.destroy()
            self.form = FormFrame(self)
            self.form.grid(row=0, column=0)

