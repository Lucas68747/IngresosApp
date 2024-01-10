from tkinter import *
from tkinter import messagebox
from tkinter import ttk
import sqlite3
from fpdf import FPDF
from datetime import datetime

# VENTANA

root = Tk()
root.title("IngresosApp")
root.geometry("610x350")
root.resizable(width=0, height=0)

miId = StringVar()
miDate = StringVar()
miHour = StringVar()
miDomain = StringVar()
miBusiness = StringVar()
miParticular = StringVar()
miDestination = StringVar()

# BASE DE DATOS

def conexionBBDD():
    miConexion = sqlite3.connect("base")
    miCursor = miConexion.cursor()

    try:
        miCursor.execute('''
            CREATE TABLE IF NOT EXISTS empleado (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            DATE VARCHAR(50) NOT NULL,
            HOUR VARCHAR(50) NOT NULL,
            DOMAIN VARCHAR(50) NOT NULL,
            BUSINESS VARCHAR(50) NOT NULL,
            PARTICULAR VARCHAR(50) NOT NULL,
            DESTINATION VARCHAR(50) NOT NULL)
            ''')
        messagebox.showinfo("Aviso", "Base de datos creada o conectada exitosamente")
    except:
        messagebox.showinfo("Aviso", "Conexión exitosa con la base de datos")

def eliminarBBDD():
    miConexion = sqlite3.connect("base")
    miCursor = miConexion.cursor()
    if messagebox.askyesno(message="Los datos serán eliminados definitivamente, ¿continuar?", title="Aviso"):
        miCursor.execute("DROP TABLE empleado")
    else:
        pass
    limpiarCampos()
    mostrar()

def salirAplicacion():
    valor = messagebox.askquestion("¿Salir?", "¿Está seguro que desea salir de la Aplicación?")
    if valor == "yes":
        root.destroy()

def limpiarCampos():
    miId.set("")
    mostrar()

def mensaje():
    acerca = '''
App Control de ingresos
Versión 1.0
Por Lucas Emanuel Santoro
'''
    messagebox.showinfo(title="Acerca de", message=acerca)

################################ MÉTODOS CRUD ##############################

def crear():
    miConexion = sqlite3.connect("base")
    miCursor = miConexion.cursor()
    try:
        fecha_actual = datetime.now().strftime('%Y-%m-%d')
        hora_actual = datetime.now().strftime('%H:%M:%S')
        datos = (
            fecha_actual,  # Fecha actual
            hora_actual,   # Hora actual
            miDomain.get(),
            miBusiness.get(),
            miParticular.get(),
            miDestination.get()
        )
        miCursor.execute("INSERT INTO empleado (DATE, HOUR, DOMAIN, BUSINESS, PARTICULAR, DESTINATION) VALUES (?, ?, ?, ?, ?, ?)", datos)
        miConexion.commit()
    except Exception as e:
        messagebox.showwarning("Aviso", f"Ocurrió un error al crear el registro: {str(e)}")
        pass
    limpiarCampos()

def mostrar():
    miConexion = sqlite3.connect("base")
    miCursor = miConexion.cursor()
    registros = tree.get_children()
    for elemento in registros:
        tree.delete(elemento)

    try:
        miCursor.execute("SELECT * FROM empleado")
        for row in miCursor:
            tree.insert("", 0, text=row[0], values=(row[1], row[2], row[3], row[4], row[5], row[6]))
    except:
        pass

################################## TABLA ################################

tree = ttk.Treeview(height=11, columns=('#0', '#1', '#2', '#3', '#4', '#5'))
tree.place(x=0, y=150)
tree.column('#0', width=50)
tree.heading('#0', text="ID", anchor=CENTER)
tree.column('#1', width=80)
tree.heading('#1', text="Fecha", anchor=CENTER)
tree.column('#2', width=80)
tree.heading('#2', text="Hora", anchor=CENTER)
tree.column('#3', width=100)
tree.heading('#3', text="Dominio", anchor=CENTER)
tree.column('#4', width=100)
tree.heading('#4', text="Empresa", anchor=CENTER)
tree.column('#5', width=100)
tree.heading('#5', text="Particular", anchor=CENTER)
tree.column('#6', width=100)
tree.heading('#6', text="Destino", anchor=CENTER)

def seleccionarUsandoClick(event):
    item = tree.identify('item', event.x, event.y)
    miId.set(tree.item(item, "text"))
    miDate.set(tree.item(item, "values")[0])
    miHour.set(tree.item(item, "values")[1])
    miDomain.set(tree.item(item, "values")[2])
    miBusiness.set(tree.item(item, "values")[3])
    miParticular.set(tree.item(item, "values")[4])
    miDestination.set(tree.item(item, "values")[5])

tree.bind("<Double-1>", seleccionarUsandoClick)

def actualizar():
    miConexion = sqlite3.connect("base")
    miCursor = miConexion.cursor()
    try:
        fecha_actual = datetime.now().strftime('%Y-%m-%d')
        hora_actual = datetime.now().strftime('%H:%M:%S')
        datos = (
            fecha_actual,  # Fecha actual
            hora_actual,   # Hora actual
            miDomain.get(),
            miBusiness.get(),
            miParticular.get(),
            miDestination.get()
        )
        miCursor.execute("UPDATE empleado SET DATE=?, HOUR=?, DOMAIN=?, BUSINESS=?, PARTICULAR=?, DESTINATION=? WHERE ID=" + miId.get(), datos)
        miConexion.commit()
    except Exception as e:
        messagebox.showwarning("Aviso", f"Ocurrió un error al actualizar el registro: {str(e)}")
        pass
    limpiarCampos()

def borrar():
    miConexion = sqlite3.connect("base")
    miCursor = miConexion.cursor()
    try:
        if messagebox.askyesno(message="¿Realmente desea eliminar el registro?", title="Aviso"):
            miCursor.execute("DELETE FROM empleado WHERE ID=" + miId.get())
            miConexion.commit()
    except:
        messagebox.showwarning("Aviso", "Ocurrió un error al tratar de eliminar el registro")
        pass
    limpiarCampos()

########## ELEMENTOS DE INTERFACE ##########

# MENÚ INICIO

menubar = Menu(root)
menubasedat = Menu(menubar, tearoff=0)
menubasedat.add_command(label="Crear/Conectar base de datos", command=conexionBBDD)
menubasedat.add_command(label="Eliminar base de datos", command=eliminarBBDD)
menubasedat.add_command(label="Salir", command=salirAplicacion)
menubar.add_cascade(label="Inicio", menu=menubasedat)

# MENÚ AYUDA

helpmenu = Menu(menubar, tearoff=0)
helpmenu.add_command(label="Limpiar campos", command=limpiarCampos)
helpmenu.add_command(label="Acerca de", command=mensaje)
menubar.add_cascade(label="Ayuda", menu=helpmenu)

# CAJAS DE DATOS

L4 = Label(root, text="Dominio")
L4.place(x=40, y=10)
E4 = Entry(root, textvariable=miDomain, width=20)
E4.place(x=120, y=10)

L5 = Label(root, text="Empresa")
L5.place(x=40, y=40)
E5 = Entry(root, textvariable=miBusiness, width=20)
E5.place(x=120, y=40)

L6 = Label(root, text="Particular")
L6.place(x=40, y=70)
E6 = Entry(root, textvariable=miParticular, width=20)
E6.place(x=120, y=70)

L7 = Label(root, text="Destino")
L7.place(x=40, y=100)
E7 = Entry(root, textvariable=miDestination, width=20)
E7.place(x=120, y=100)

# ESTILO Y BOTONES

style = ttk.Style()
style.configure('my.TButton', font=('Arial', 10,))

B1 = ttk.Button(root, text="Agregar entrada", width=16, command=crear, style='my.TButton')
B1.place(x=300, y=10)

B2 = ttk.Button(root, text="Modificar entrada", width=16, command=actualizar, style='my.TButton')
B2.place(x=300, y=40)

B3 = ttk.Button(root, text="Mostrar lista", width=16, command=mostrar, style='my.TButton')
B3.place(x=300, y=70)

B4 = ttk.Button(root, text="Eliminar entrada", width=16, command=borrar, style='my.TButton')
B4.place(x=300, y=100)

root.config(menu=menubar)

###################### FPDF ######################

def exportar():
    miConexion = sqlite3.connect("base")
    miCursor = miConexion.cursor()
    try:
        miCursor.execute("SELECT * FROM empleado")
        resultados = miCursor.fetchall()
    except:
        messagebox.showwarning("Aviso", "Ocurrió un error al leer la base de datos")
        return

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)

    pdf.cell(200, 10, txt="Ingresos del día de la fecha", ln=1, align="C")
    pdf.cell(25, 10, txt="ID", ln=1, align="L")
    pdf.cell(25, 10, txt="Fecha", ln=0, align="L")
    pdf.cell(25, 10, txt="Hora", ln=0, align="L")
    pdf.cell(35, 10, txt="Dominio", ln=0, align="L")
    pdf.cell(35, 10, txt="Empresa", ln=0, align="L")
    pdf.cell(35, 10, txt="Particular", ln=0, align="L")
    pdf.cell(35, 10, txt="Destino", ln=1, align="L")

    for row in resultados:
        pdf.cell(25, 10, txt=str(row[0]), ln=1, align="L")
        pdf.cell(25, 10, txt=row[1], ln=0, align="L")
        pdf.cell(25, 10, txt=row[2], ln=0, align="L")
        pdf.cell(35, 10, txt=row[3], ln=0, align="L")
        pdf.cell(35, 10, txt=row[4], ln=0, align="L")
        pdf.cell(35, 10, txt=row[5], ln=0, align="L")
        pdf.cell(35, 10, txt=row[6], ln=1, align="L")

    pdf.output("tabla_ingresos.pdf")

exportar_btn = ttk.Button(root, text="Exportar a PDF", width=16, command=exportar, style='my.TButton')
exportar_btn.place(x=460, y=60)

root.mainloop()
