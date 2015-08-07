import os
import platform
import settings


def ping_test(target):
    if platform.system() == "Windows":
        response = os.system("ping " + target + " -n 1 -w 500")
    else:
        response = os.system("ping -c 2 " + target)
    is_up = False
    if response == 0:
        is_up = True
    return is_up


def is_pingable(server):
    return ping_test(server) and ping_test(server)


import ssh
import socket


def ssh_connect(server, username, password):
    try:
        client = ssh.SSHClient()
        client.set_missing_host_key_policy(ssh.AutoAddPolicy())
        client.connect(server, username=username, password=password)
        return client
    except socket.timeout:
        return 0


import Tkinter
import tkMessageBox
import threading
import Queue
import select
import logging
import shutil
from datetime import datetime


class DiagnosticWindow(object):

    def __init__(self, master, set_indicator_stopped):
        self.master = master
        self.master.focus()

        self.running = 1
        self.queue = Queue.Queue()
        self.thread = threading.Thread(target=self.worker_thread)
        self.thread.start()
        self.periodic_call()

        self.set_indicator_stopped = set_indicator_stopped

        self.autoscroll_enabled = Tkinter.IntVar()
        self.autoscroll_enabled.set(1)

        self.scrollbar = Tkinter.Scrollbar(self.master)
        self.scrollbar.pack(side=Tkinter.RIGHT, fill=Tkinter.Y)

        self.diagnostic_output = Tkinter.Text(self.master,
                                              height=32,
                                              width=66,
                                              foreground='grey',
                                              background='black',
                                              yscrollcommand=self.scrollbar,
                                              state=Tkinter.DISABLED,
                                              wrap=Tkinter.NONE,
                                              )

        self.diagnostic_output.pack(fill=Tkinter.BOTH, expand=1)
        self.scrollbar.config(command=self.diagnostic_output.yview)

        self.save_log_button = Tkinter.Button(self.master,
                                              text='Save',
                                              width=25,
                                              height=3,
                                              command=self.save_diagnostic_to_file,
                                              )
        self.save_log_button.pack(side=Tkinter.RIGHT)

        self.autoscroll_checkbox = Tkinter.Checkbutton(self.master,
                                                       text='Autoscroll',
                                                       variable=self.autoscroll_enabled,
                                                       )
        self.autoscroll_checkbox.pack(side=Tkinter.LEFT)

        self.ok_button = Tkinter.Button(self.master,
                                        text='OK',
                                        width=25,
                                        height=3,
                                        command=self.close_window
                                        )
        self.ok_button.pack(side=Tkinter.RIGHT)

    def save_diagnostic_to_file(self):
        log = self.diagnostic_output.get("1.0", Tkinter.END)
        filename = datetime.now().strftime('%Y%m%d-%H%M%S_diagnostic.log')
        tkMessageBox.showinfo("Save diagnostic log",
                              "Saving file: %s" % filename,
                              parent=self.save_log_button,
                              )
        with open(filename, 'w') as f:
            f.write(log)

    def close_window(self):
        self.running = 0
        self.set_indicator_stopped()
        self.master.destroy()

    def periodic_call(self):
        """
        Check every 100 ms if there is something new in the queue.
        """
        try:
            self.process_incoming()
        except AttributeError:
            logging.exception("AttributeError in process_incoming from periodic_call")

        if not self.running:
            import sys
            sys.exit(1)
        self.master.after(100, self.periodic_call)

    def worker_thread(self):
        """
        This is where we handle the asynchronous I/O.
        """
        if is_pingable(settings.server):
            ssh_client = ssh_connect(settings.server, settings.username, settings.password)
            if ssh_client:
                try:
                    while self.running:
                        try:
                            (stdin, stdout, stderr) = ssh_client.exec_command(settings.diagnostic_command)
                            msg = stdout.read()
                            self.queue.put(msg)
                        except ssh.SSHException:
                            logging.exception('SSH Exception')
                            self.set_indicator_stopped()
                            break
                        except EOFError:
                            logging.exception('EOFError')
                            break
                        except socket.error:
                            logging.exception('Socket error. Connection lost.')
                            break
                        except:
                            logging.exception('Exception')
                            break
                except socket.timeout:
                    logging.exception('SSH Connection timeout')
                finally:
                    if ssh_client:
                        ssh_client.close()
        else:
             print "Server not pingable!"

    def process_incoming(self):
        """
        Handle all the messages currently in the queue (if any).
        """
        while self.queue.qsize():
            if self.running:
                try:
                    msg = self.queue.get(0)
                    numlines = int(self.diagnostic_output.index('end - 1 line').split('.')[0])
                    if numlines >= 500:
                        for n in range(numlines - 500):
                            self.diagnostic_output.config(state=Tkinter.NORMAL)
                            self.diagnostic_output.delete(1.0, 2.0)
                            self.diagnostic_output.config(state=Tkinter.DISABLED)
                    self.diagnostic_output.config(state=Tkinter.NORMAL)
                    self.diagnostic_output.insert(Tkinter.END, msg)
                    self.diagnostic_output.config(state=Tkinter.DISABLED)
                    if self.autoscroll_enabled.get():
                        self.diagnostic_output.see(Tkinter.END)
                        self.diagnostic_output.xview(Tkinter.MOVETO, 0.0)
                except self.queue.empty():
                    pass


class LogWindow(object):

    def __init__(self, master, set_indicator_stopped):
        self.master = master
        self.master.focus()
        self.set_indicator_stopped = set_indicator_stopped
        self.start_time = datetime.now().strftime('%Y%m%d-%H%M%S')
        self.running = 1
        self.queue = Queue.Queue()
        self.queue.put('')
        self.queue.put('Using username "%s".\n' % settings.username)
        self.queue.put("%s@%s's password: \n" % (settings.username, settings.server))
        self.thread = threading.Thread(target=self.worker_thread)
        self.thread.start()
        self.periodic_call()

        self.autoscroll_enabled = Tkinter.IntVar()
        self.autoscroll_enabled.set(1)
        self.wrap_enabled = Tkinter.IntVar()

        self.scrollbar = Tkinter.Scrollbar(self.master)
        self.scrollbar.pack(side=Tkinter.RIGHT, fill=Tkinter.Y)

        self.log_output = Tkinter.Text(self.master,
                                       height=32,
                                       width=120,
                                       foreground='grey',
                                       background='black',
                                       yscrollcommand=self.scrollbar,
                                       state=Tkinter.DISABLED,
                                       wrap=Tkinter.NONE,
                                       )
        self.log_output.pack(fill=Tkinter.BOTH, expand=1)
        self.scrollbar.config(command=self.log_output.yview)

        self.save_log_button = Tkinter.Button(self.master,
                                              text='Save',
                                              width=25,
                                              height=3,
                                              command=self.pinch_log_to_file,
                                              )
        self.save_log_button.pack(side=Tkinter.RIGHT)

        self.autoscroll_checkbox = Tkinter.Checkbutton(self.master,
                                                       text='Autoscroll',
                                                       variable=self.autoscroll_enabled,
                                                       )
        self.autoscroll_checkbox.pack(side=Tkinter.LEFT)

        self.wrap_checkbox = Tkinter.Checkbutton(self.master,
                                                 text='Wrap',
                                                 variable=self.wrap_enabled,
                                                 command=self.set_wrap,
                                                 )
        self.wrap_checkbox.pack(side=Tkinter.LEFT)

        self.ok_button = Tkinter.Button(self.master,
                                        text='OK',
                                        width=25,
                                        height=3,
                                        command=self.close_window
                                        )
        self.ok_button.pack(side=Tkinter.RIGHT)

    def close_window(self):
        self.running = 0
        self.set_indicator_stopped()
        self.master.destroy()

    def periodic_call(self):
        """
        Check every 100 ms if there is something new in the queue.
        """
        try:
            self.process_incoming()
        except AttributeError:
            pass

        if not self.running:
            import sys
            sys.exit(1)
        self.master.after(100, self.periodic_call)

    def worker_thread(self):
        """
        This is where we handle the asynchronous I/O.
        """
        if is_pingable(settings.server):
            ssh_client = ssh_connect(settings.server, settings.username, settings.password)
            if ssh_client:
                try:
                    transport = ssh_client.get_transport()
                    channel = transport.open_session()
                    channel.exec_command(settings.log_command)
                    while self.running:
                        rl, wl, xl = select.select([channel], [], [], 0.0)
                        if len(rl) > 0:
                            msg = channel.recv(4096)
                            self.queue.put(msg)
                except ssh.SSHException:
                    logging.exception('SSH Exception')
                    self.set_indicator_stopped()
                except EOFError:
                    logging.exception('EOFError')
                except socket.error:
                    logging.exception('Socket error. Connection lost.')
                finally:
                    if ssh_client:
                        ssh_client.close()
        else:
             print "Server not pingable!"

    def process_incoming(self):
        """
        Handle all the messages currently in the queue (if any).
        """
        def append_to_log_output(message):
            numlines = int(self.log_output.index('end - 1 line').split('.')[0])
            if numlines >= 500:
                for n in range(numlines - 500):
                    self.log_output.config(state=Tkinter.NORMAL)
                    self.log_output.delete(1.0, 2.0)
                    self.log_output.config(state=Tkinter.DISABLED)
            self.log_output.config(state=Tkinter.NORMAL)
            self.log_output.insert(Tkinter.END, message)
            self.log_output.config(state=Tkinter.DISABLED)

        self.log_filename = ''.join((self.start_time, '_log.log'))

        while self.queue.qsize() and self.running:
            try:
                msg = self.queue.get(0)
                append_to_log_output(msg)
                with open(self.log_filename, 'a') as f:
                    f.write(msg)
                if self.autoscroll_enabled.get():
                    self.log_output.see(Tkinter.END)
                    self.log_output.xview(Tkinter.MOVETO, 0.0)
            except self.queue.empty():
                pass

    def pinch_log_to_file(self):
        pinch_filename = ''.join((self.start_time,
                                  '_log_pinched_off_at_',
                                  datetime.now().strftime('%Y%m%d-%H%M%S.log')))
        shutil.copyfile(self.log_filename, pinch_filename)
        if os.path.isfile(pinch_filename):
            tkMessageBox.showinfo("Pinch off log log",
                                  "Saving file: %s" % pinch_filename,
                                  parent=self.save_log_button,
                                  )
        else:
            tkMessageBox.showinfo("Pinch off log log",
                                  "Saving file failed: %s" % pinch_filename,
                                  parent=self.save_log_button,
                                  )

    def set_wrap(self):
        if self.wrap_enabled.get():
            self.log_output.config(wrap=Tkinter.CHAR)
        elif not self.wrap_enabled.get():
            self.log_output.config(wrap=Tkinter.NONE)


class MainWindow(object):

    def __init__(self, master):
        self.master = master
        self.ping_button = Tkinter.Button(master,
                                          text='ping',
                                          command=self.run_ping_button,
                                          width=25,
                                          height=4,
                                          )
        self.ping_button.grid(row=0)

        self.ping_indicator_canvas = Tkinter.Canvas(master, width=200, height=70)
        self.ping_indicator_canvas.grid(row=0, column=1)
        self.ping_indicator_rect = self.ping_indicator_canvas.create_rectangle(50, 10, 150, 64, fill="red")
        self.ping_indicator_text = self.ping_indicator_canvas.create_text(100, 37.5, text="Stopped")

        self.diagnostic_button = Tkinter.Button(master,
                                                text='diagnostic',
                                                command=self.launch_diagnostic_window,
                                                width=25,
                                                height=4,
                                                )
        self.diagnostic_button.grid(row=2)

        self.diagnostic_indicator_canvas = Tkinter.Canvas(master, width=200, height=70)
        self.diagnostic_indicator_canvas.grid(row=2, column=1)
        self.diagnostic_indicator_rect = self.diagnostic_indicator_canvas.create_rectangle(50, 10, 150, 64, fill="red")
        self.diagnostic_indicator_text = self.diagnostic_indicator_canvas.create_text(100, 37.5, text="Stopped")

        self.log_button = Tkinter.Button(master,
                                         text='log',
                                         command=self.start_log_log,
                                         width=25,
                                         height=4,
                                         )
        self.log_button.grid(row=4)

        self.log_indicator_canvas = Tkinter.Canvas(master, width=200, height=70)
        self.log_indicator_canvas.grid(row=4, column=1)
        self.log_indicator_rect = self.log_indicator_canvas.create_rectangle(50, 10, 150, 64, fill="red")
        self.log_indicator_text = self.log_indicator_canvas.create_text(100, 37.5, text="Stopped")

        self.quit_button = Tkinter.Button(master,
                                          text='quit',
                                          command=self.exit_app,
                                          width=25,
                                          height=4)
        self.quit_button.grid(row=5)
        self.quit_placeholder_canvas = Tkinter.Canvas(master, width=200, height=70)
        self.quit_placeholder_canvas.grid(row=5, column=1)

    def show_loss_of_comm_alert(self):
        tkMessageBox.showwarning(
            "Alert",
            "Loss of comm with server. Ping test failed."
        )

    def run_ping_button(self):
        if is_pingable(settings.server):
            self.set_ping_indicator_passed()
            return True
        else:
            self.set_ping_indicator_failed()
            self.show_loss_of_comm_alert()
            return False

    def close_diagnostic_window(self):
        self.diagnostic_gui.close_window()
        self.set_diagnostic_indicator_stopped()

    def close_log_window(self):
        self.log_gui.close_window()
        self.set_log_indicator_stopped()

    def exit_app(self):
        try:
            self.close_diagnostic_window()
        except AttributeError:
            pass

        try:
            self.close_log_window()
        except AttributeError:
            pass

        self.master.destroy()

    def set_ping_indicator_passed(self):
        self.ping_indicator_canvas.itemconfig(self.ping_indicator_rect, fill="green")
        self.ping_indicator_canvas.itemconfig(self.ping_indicator_text, text="Passed")

    def set_ping_indicator_failed(self):
        self.ping_indicator_canvas.itemconfig(self.ping_indicator_rect, fill="red")
        self.ping_indicator_canvas.itemconfig(self.ping_indicator_text, text="Failed")

    def set_diagnostic_indicator_running(self):
        self.diagnostic_indicator_canvas.itemconfig(self.diagnostic_indicator_rect, fill="green")
        self.diagnostic_indicator_canvas.itemconfig(self.diagnostic_indicator_text, text="Running")

    def set_diagnostic_indicator_stopped(self):
        self.diagnostic_indicator_canvas.itemconfig(self.diagnostic_indicator_rect, fill="red")
        self.diagnostic_indicator_canvas.itemconfig(self.diagnostic_indicator_text, text="Stopped")

    def set_log_indicator_running(self):
        self.log_indicator_canvas.itemconfig(self.diagnostic_indicator_rect, fill="green")
        self.log_indicator_canvas.itemconfig(self.diagnostic_indicator_text, text="Running")

    def set_log_indicator_stopped(self):
        self.log_indicator_canvas.itemconfig(self.log_indicator_rect, fill="red")
        self.log_indicator_canvas.itemconfig(self.log_indicator_text, text="Stopped")

    def launch_diagnostic_window(self):
        try:
            self.diagnostic_window.deiconify()
        except:
            if is_pingable(settings.server):
                self.set_ping_indicator_passed()
                self.diagnostic_window = Tkinter.Toplevel(self.master)
                self.diagnostic_window.protocol("WM_DELETE_WINDOW", self.close_diagnostic_window)
                self.diagnostic_window.title("diagnostic")
                self.diagnostic_gui = DiagnosticWindow(self.diagnostic_window, self.set_diagnostic_indicator_stopped)
                self.set_diagnostic_indicator_running()
            else:
                self.show_loss_of_comm_alert()
                self.set_ping_indicator_failed()

    def start_log_log(self):
        try:
            self.log_window.deiconify()
        except:
            if is_pingable(settings.server):
                self.set_ping_indicator_passed()
                self.log_window = Tkinter.Toplevel(self.master)
                self.log_window.protocol("WM_DELETE_WINDOW", self.close_log_window)
                self.log_window.title("log")
                self.log_gui = LogWindow(self.log_window, self.set_log_indicator_stopped)
                self.set_log_indicator_running()
            else:
                self.show_loss_of_comm_alert()
                self.set_ping_indicator_failed()


def main():
    root = Tkinter.Tk()
    client = MainWindow(root)
    root.title("ta")
    root.protocol("WM_DELETE_WINDOW", client.exit_app)
    root.mainloop()

if __name__ == '__main__':
    main()