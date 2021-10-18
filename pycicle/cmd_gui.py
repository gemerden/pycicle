import os.path
import tkinter as tk
from tkinter import ttk
from tkinter.filedialog import asksaveasfilename, askopenfilename, askdirectory, askopenfilenames

from pycicle.basetypes import FileBase, FolderBase, ChoiceBase
from pycicle.help_funcs import get_parser_help, get_argument_help
from pycicle.tools.document import short_line
from pycicle.tools.tktooltip import CreateToolTip
from pycicle.tools.utils import MISSING, TRUE, FALSE, redirect_output


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


class TooltipMixin(object):
    def __init__(self, *args, tooltip=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tooltip(tooltip)

    def tooltip(self, text):
        if text is not None:
            CreateToolTip(self, text)

    def config(self, tooltip=None, **kwargs):
        super().config(**kwargs)
        self.tooltip(tooltip)


class Frame(TooltipMixin, tk.Frame):
    pass


class Button(TooltipMixin, tk.Button):
    pass


class Entry(TooltipMixin, tk.Entry):
    pass


class Combobox(TooltipMixin, ttk.Combobox):
    pass


class OutputDialog(tk.Toplevel):
    """ A general class for redirecting I/O to this Text widget. """

    def __init__(self, master, title='output', xy=(400, 400),
                 wh=None, fg='white', bg='black', font=('Helvetica', 9, 'bold')):
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


class BaseFrame(Frame):
    norm_font = ('Helvetica', 10, 'normal')
    bold_font = ('Helvetica', 10, 'bold')
    head_config = {'font': bold_font, 'anchor': tk.W}
    cell_config = {'font': norm_font}
    grid_config = {'padx': 4, 'pady': 1, 'sticky': tk.W}

    def __init__(self, master=None, **kwargs):
        super().__init__(master)
        self._init(**kwargs)  # before create_widgets
        self.create_widgets()

    def _init(self, **kwargs):
        """" override for initialization before widgets are created """
        pass

    def create_widgets(self):
        raise NotImplementedError


def show_multi_choice_dialog(window, title, chosen, xy, wh=None):
    dialog = _get_dialog(window, title, wh=wh, xy=xy)
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
        chosen.update({c: var.get() for c, var in chosen_vars.items()})
        dialog.destroy()

    ok_button = Button(dialog, text='OK', command=on_ok, width=6)
    ok_button.grid(row=len(chosen), column=1, padx=4, pady=5)
    dialog.wait_window()


class ArgWrapper(object):
    """
    'translation' class between parser arguments and the gui; e.g. responsible for creating widgets for different types
    and argument configurations.
    """
    strings = {
        'name': lambda arg: ('*' if arg.required else '') + arg.name,
        'type': lambda arg: arg.type.__name__,
        'many': lambda arg: 'yes' if arg.many else 'no',
    }
    alert_config = {
        'highlightthickness': 1,
        'highlightcolor': "red",
        'highlightbackground': "red",
    }

    def __init__(self, app, argument):
        self.app = app
        self.arg = argument
        self.var = None
        self.factory = {bool: self._get_choice_value_widget,
                        FileBase: self._get_file_value_widget,
                        FolderBase: self._get_folder_value_widget,
                        ChoiceBase: self._get_choice_value_widget}
        self.widget = None
        self.help_button = None
        self.error = None

    @property
    def kwargs(self):  # to edit the actual args
        return self.app.parser.kwargs

    def get_value(self):
        value = getattr(self.kwargs,
                        self.arg.name,
                        MISSING)
        string = self.arg.encode(value)
        if self.var is None:
            self.var = tk.StringVar()
        self.var.set(string)

    def set_value(self, event=None):
        try:
            setattr(self.kwargs,
                    self.arg.name,
                    self.var.get().strip())
        except Exception as error:  # to also catch TclError, ArgumentTypeError
            if not isinstance(self.widget, ttk.Combobox):
                self.widget.config(**self.alert_config)
            self.help_button.config(fg='red')
            self.error = str(error)
        else:
            # ttk widgets do not have 'highlightthickness', but comboboxes cannot accept invalid values
            if not isinstance(self.widget, ttk.Combobox):
                self.widget.config(highlightthickness=0)
            self.help_button.config(fg='black')
            self.error = None
        self.widget.tooltip(self.error)
        return self.error is None

    def del_value(self):
        delattr(self.kwargs,
                self.arg.name)
        self.get_value()

    def create_widget(self, master, name, **kwargs):
        if name == 'value':
            return self._get_value_widget(master, **kwargs)
        if name == 'help':
            return self._get_help_button(master, **kwargs)
        return tk.Label(master, text=self.strings[name](self.arg), **kwargs)

    def _get_help_button(self, master, **kwargs):
        def show():
            w, h = (480, 360)
            x = self.help_button.winfo_rootx() + self.help_button.winfo_width() + 5
            y = self.help_button.winfo_rooty() - h - 30
            help_text = get_argument_help(self.arg, error=self.error, separator=short_line)
            show_text_dialog(self.app.master, title=f"help: {self.arg.name}",
                             text=help_text, wh=(w, h), xy=(x, y))

        self.help_button = Button(master, text='?', width=2, command=show, tooltip='more info', **kwargs)
        return self.help_button

    def _get_value_widget(self, master, **kwargs):
        self.get_value()
        for cls, widget_getter in self.factory.items():
            if issubclass(self.arg.type, cls):
                self.widget = widget_getter(master, **kwargs)
                break
        else:
            self.widget = self._get_string_value_widget(master, **kwargs)
        return self.widget

    def _get_string_value_widget(self, master, **kwargs):
        widget = Entry(master, textvariable=self.var, **kwargs)
        widget.bind('<KeyRelease>', self.set_value)
        return widget

    def _get_dialog_value_widget(self, master, command, **kwargs):
        widget = Frame(master=master)

        entry_field = Entry(widget, textvariable=self.var, **kwargs)
        entry_field.bind('<KeyRelease>', self.set_value)
        entry_field.pack(side=tk.LEFT, fill=tk.X)

        file_button = Button(widget, text='...', command=command, tooltip='select')
        file_button.pack(side=tk.RIGHT, fill=tk.X, padx=(4, 0))
        return widget

    def _get_file_value_widget(self, master, **kwargs):
        def open_file_dialog():
            filetypes = [('', '.' + ext) for ext in self.arg.type.extensions]
            if self.arg.many:  # append in case of many
                filenames = askopenfilenames(filetypes=filetypes)
                self.var.set(f"{self.var.get()} {', '.join(filenames)}")
            else:
                filename = askopenfilename(filetypes=filetypes)
                self.var.set(filename)
            self.set_value()

        return self._get_dialog_value_widget(master, command=open_file_dialog, **kwargs)

    def _get_folder_value_widget(self, master, **kwargs):
        def open_folder_dialog():
            foldername = askdirectory(mustexist=self.arg.type.existing)
            if self.arg.many:  # append in case of many
                self.var.set(f"{self.var.get()} {foldername}")
            else:
                self.var.set(foldername)
            self.set_value()

        return self._get_dialog_value_widget(master, command=open_folder_dialog, **kwargs)

    def _get_choice_value_widget(self, master, **kwargs):
        choices = list(getattr(self.arg.type, 'choices', (FALSE, TRUE)))
        if self.arg.many:
            return self._get_multi_choice_value_widget(master, choices, **kwargs)
        return self._get_single_choice_value_widget(master, choices, **kwargs)

    def _get_single_choice_value_widget(self, master, choices, **kwargs):
        def on_select(event):
            self.var.set(widget.get())
            self.set_value()

        default = self.arg.encode(self.arg.default)
        if default in choices:
            choices.remove(default)
        choices.insert(0, default)

        widget = Combobox(master, values=choices,
                          textvariable=self.var,
                          state="readonly", **kwargs)
        widget.bind("<<ComboboxSelected>>", on_select)
        return widget

    def _get_multi_choice_value_widget(self, master, choices, **kwargs):
        values = self.var.get().split(' ')
        chosen = {c: (c in values) for c in choices}

        def show():
            x = self.app.winfo_rootx() + self.app.winfo_width() + 8
            y = self.app.winfo_rooty() - 64
            show_multi_choice_dialog(self.app.master, title=f"{self.arg.name}",
                                     chosen=chosen, xy=(x, y))
            self.var.set(' '.join(c for c, b in chosen.items() if b))
            self.set_value()

        return self._get_dialog_value_widget(master, command=show, **kwargs)


# ==================================================================

class FormFrame(BaseFrame):
    column_grid_configs = {'name': {'sticky': tk.E},  # overrides grid_config
                           'value': {'sticky': tk.EW},
                           'type': {},
                           'many': {'sticky': None},
                           'help': {}}
    column_cell_configs = {'value': {'width': 56}}

    def _init(self):
        self.wrappers = [ArgWrapper(self.master, argument=arg) for arg in self.master.arguments]

    def create_widgets(self):
        def cell_config(col_name):
            return dict(self.cell_config, **self.column_cell_configs.get(col_name, {}))

        def grid_config(col_name):
            return dict(self.grid_config, **self.column_grid_configs.get(col_name, {}))

        for i, name in enumerate(self.column_grid_configs):
            tk.Label(self, text=name, **self.head_config) \
                .grid(row=0, column=i)
        for i, wrapper in enumerate(self.wrappers):
            for j, name in enumerate(self.column_grid_configs):
                wrapper.create_widget(self, name=name, **cell_config(name)) \
                    .grid(row=i + 1, column=j, **grid_config(name))


class CommandFrame(BaseFrame):
    button_configs = {'short': {'text': '><',
                                'tooltip': 'short: select to see command line with short flags (like -f)'},
                      'path': {'text': '\\..\\',
                               'tooltip': 'path: select to see command line with full path to python script'},
                      'list': {'text': '[..]',
                               'tooltip': 'list: show the commands on the command line as a list'}}

    def _init(self):
        self.selected = {'short': False, 'path': False, 'list': False}
        self.buttons = {}

    def create_widgets(self):
        def switch(button_name):
            def inner():
                selected = self.selected[button_name] = not self.selected[button_name]
                self.buttons[button_name].config(relief=tk.SUNKEN if selected else tk.RAISED)
                self.show_command()

            return inner

        def get_button(name):
            return Button(self, command=switch(name), font=self.norm_font, **self.button_configs[name])

        for name in self.selected:
            self.buttons[name] = get_button(name)
            self.buttons[name].pack(side=tk.LEFT)

        self.command_view = FittingText(self, width=72, height=1, font=self.norm_font)
        self.command_view.pack(side=tk.LEFT, fill=tk.X, padx=5)

    def show_command(self):
        cmd = self.master.command(**self.selected)
        self.command_view.config(state=tk.NORMAL)
        self.command_view.delete(1.0, tk.END)
        if cmd is not None:
            self.command_view.insert(1.0, cmd)
        self.command_view.config(state=tk.DISABLED)


class ButtonBar(BaseFrame):
    button_configs = dict(
        check={'tooltip': 'check the currently filled in values'},
        run={'tooltip': 'run the script with these command line arguments'},
        save={'tooltip': 'save the command line to the same file'},
        save_as={'tooltip': 'save the command line to file'},
        load={'tooltip': 'load the command line from file'},
        reset={'tooltip': 'reset all values to default or empty'},
        help={'text': '?', 'width': 2, 'tooltip': 'docs on this program and its use'}
    )

    grid_config = {'padx': 2, 'pady': 2}
    default_button_config = {'width': 6, 'font': ('Helvetica', 10, 'normal')}

    def _init(self):
        self.buttons = {}

    def create_widgets(self):
        for name, config in self.button_configs.items():
            self.buttons[name] = self.get_button(name, config)
        self.config(padx=5, pady=5)

    def get_button(self, name, config):
        config['text'] = config.get('text', name.replace('_', ' '))
        button = Button(self, command=getattr(self.master, name),
                        **dict(self.default_button_config, **config))
        button.grid(row=0, column=len(self.buttons), **self.grid_config)
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

    def set_values(self):
        success = True
        for wrapper in self.form.wrappers:
            success &= wrapper.set_value()
        self.command_frame.show_command()
        return success

    def get_values(self):
        for wrapper in self.form.wrappers:
            wrapper.get_value()
        self.command_frame.show_command()

    def del_values(self):
        for wrapper in self.form.wrappers:
            wrapper.del_value()
        self.command_frame.show_command()

    def command(self, short=False, path=False, list=False):
        cmd_line = self.parser.command(short=short, prog=True, path=path)
        if list:
            return str(cmd_line.split())
        return cmd_line

    def check(self):
        self.set_values()

    def run(self):
        if self.target is None:
            tk.messagebox.showinfo('nothing to run', 'no runnable target was configured for this app')
        elif self.set_values():
            dialog = OutputDialog(self.master)
            with redirect_output(dialog):
                print('running: ', self.command(), '\n')
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
        self.del_values()

    def help(self):
        help_text = get_parser_help(self.parser)
        x = self.winfo_rootx() + self.winfo_width() + 20
        y = self.winfo_rooty() - 36
        show_text_dialog(self.master, 'help', help_text, wh=(640, 640), xy=(x, y))
