import discord
import json
import httpx
import os
from groq import Groq
import time
from datetime import datetime
import random
from PyPDF2 import PdfReader
import asyncio
from discord.ext import commands
from discord.ui import View, Button, Select
from dotenv import load_dotenv

load_dotenv("TOKEN.env")  # Carga el archivo .env

TOKEN = os.getenv("TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True


bot = commands.Bot(command_prefix='!', intents=intents)
client= Groq(api_key=GROQ_API_KEY)

# BIENVENIDA Y TÉRMINOS
JSON_PATH = "alejandrinos.json"

def cargar_datos():
    try:
        with open(JSON_PATH, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"contador": 1, "usuarios": {}}

def guardar_datos(datos):
    with open(JSON_PATH, "w") as f:
        json.dump(datos, f, indent=4)

def guardar_id_mensaje(canal_id, tipo, mensaje_id, ruta="mensajes.json"):
    data = {}
    if os.path.exists(ruta):
        with open(ruta, "r") as f:
            data = json.load(f)
    
    canal_str = str(canal_id)
    if canal_str not in data:
        data[canal_str] = {}
    
    data[canal_str][tipo] = mensaje_id

    with open(ruta, "w") as f:
        json.dump(data, f)

def obtener_id_mensaje(canal_id, tipo, ruta="mensajes.json"):
    if not os.path.exists(ruta):
        return None
    with open(ruta, "r") as f:
        data = json.load(f)
    
    return data.get(str(canal_id), {}).get(tipo)

@bot.event
async def on_ready():
    print(f"✅ Alejandro está conectado como {bot.user.name}")

    await bot.wait_until_ready()

    # 🔹 Buscar canal por nombre "subidas"
    canal = discord.utils.get(bot.get_all_channels(), name="subidas")
    print("📺 Canal encontrado por nombre:", canal)

    if not canal:
        print("❌ No se encontró el canal 'subidas'")
        return

    # 🔹 Enviar la vista (botón para comenzar la subida)
    try:
        
        mensaje_id = obtener_id_mensaje(canal.id, "subida")
        mensaje = await canal.fetch_message(mensaje_id)

        if mensaje:
            print("📌 Mensaje del botón ya existe.")
           
        else:
            view = SubidaView()
            mensaje = await canal.send("Haz clic para comenzar la subida:", view=view)
            guardar_id_mensaje(canal.id, "subida", mensaje.id)
            print("✅ Mensaje del botón creado.")

    except Exception as e:
        print("❌ Error al enviar la vista:", e)

    # 🔹 Crear o reutilizar mensaje de estado (tokens)
    try:
        mensaje_id = obtener_id_mensaje(canal.id, "contador")
        print(f"🔍 Obteniendo mensaje ID: {mensaje_id} del canal {canal.id}")
        try:
            mensaje = await canal.fetch_message(mensaje_id)
        except:
            mensaje = None
            print("⚠️ No se encontró el mensaje de estado, crearemos uno nuevo.")

        print(f"🔄 Actualizando mensaje ID: {mensaje_id} en canal {canal.id}")

        if mensaje:
            print("ℹ️ Mensaje de estado ya existe")

        else:
            mensaje= await canal.send(f"# 📦 Archivos restantes para subida hoy: calculando...")
            guardar_id_mensaje(canal.id,"contador", mensaje.id)
            print("✅ Mensaje de estado creado")
            
    except Exception as e:
        print("❌ Error al manejar mensaje de estado:", e)
  

@bot.event
async def on_member_join(member):
    guild = member.guild

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        member: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
    }

    canal = await guild.create_text_channel(
        name=f"bienvenida-{member.name}",
        overwrites=overwrites,
        reason="Canal temporal de bienvenida"
    )

    embed = discord.Embed(
        title="📜 Términos y Condiciones de Alejandría",
        description=(
            "1. 📚 Respetarás a todos los miembros, sus ideas y aportes.\n"
            "2. 🧠 Compartirás información útil y bien argumentada.\n"
            "3. 🔇 Nada de spam ni ataques personales.\n"
            "4. 🚫 A la tercera infracción, pierdes el acceso. Los strikes se gestionan **privadamente** y pueden ser reclamados.\n"
            "5. 🎉 **Diviértete y aprende mucho.**"
        ),
        color=discord.Color.blue()
    )

    view = View()

    class AceptarButton(Button):
        def __init__(self):
            super().__init__(label="Aceptar y entrar", style=discord.ButtonStyle.success)

        async def callback(self, interaction: discord.Interaction):
            datos = cargar_datos()
            contador = datos["contador"]

            rol = discord.utils.get(guild.roles, name="Alejandrino")
            if rol:
                await member.add_roles(rol)
            else:
                await interaction.response.send_message("❌ No se encontró el rol 'Alejandrino'.", ephemeral=True)
                return

            nuevo_apodo = f"{member.name} (Ale#{contador})"
            try:
                await member.edit(nick=nuevo_apodo)
            except discord.Forbidden:
                await interaction.response.send_message("⚠️ No tengo permisos para cambiar tu apodo.", ephemeral=True)
                return

            datos["usuarios"][str(member.id)] = nuevo_apodo
            datos["contador"] += 1
            guardar_datos(datos)

            await interaction.response.send_message("✅ Acceso concedido. Bienvenido a Alejandría.", ephemeral=True)
            await canal.delete()

    view.add_item(AceptarButton())
    await canal.send(embed=embed, view=view)

# SUBIR ARCHIVO 
class SubidaView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="📁 Subir archivo", custom_id="boton_subida", style=discord.ButtonStyle.primary))

class MenuCanalesView(View):
    def __init__(self, mensaje_original, canal_temporal, titulo):
        super().__init__(timeout=60)
        self.mensaje_original = mensaje_original
        self.canal_temporal = canal_temporal
        self.titulo = titulo


        select = Select(
            placeholder="¿A qué canal lo enviamos?",
            options=[
                # Ciencias
                discord.SelectOption(label="🔬 Biología", value="biología"),
                discord.SelectOption(label="🧲 Física", value="física"),
                discord.SelectOption(label="⚗️ Química", value="química"),
                discord.SelectOption(label="🪨 Geología", value="geología"),
                discord.SelectOption(label="📐 Matemáticas", value="matemáticas"),
                discord.SelectOption(label="💻 Informática", value="informática"),

                # Sociales
                discord.SelectOption(label="🗣️ Lenguas", value="lenguas"),
                discord.SelectOption(label="📚 Literatura", value="literatura"),
                discord.SelectOption(label="📜 Historia", value="historia"),
                discord.SelectOption(label="🌍 Geografía", value="geografía"),
                discord.SelectOption(label="💰 Economía", value="economía"),
                discord.SelectOption(label="🧠 Psicología", value="psicología"),
            ],
            custom_id="selector_canal"
        )

        select.callback = self.select_callback
        self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        canal_nombre = interaction.data["values"][0]
        canal_destino = discord.utils.get(interaction.guild.text_channels, name=canal_nombre)

        if canal_destino:
            for adjunto in self.mensaje_original.attachments:
                archivo = await adjunto.to_file()
                await canal_destino.send(
            content=f"# {self.titulo}\n📎 Archivo de {self.mensaje_original.author.mention}",file=archivo)            
            await interaction.response.send_message("✅ Archivo movido. Cerrando el canal...", ephemeral=True)
            await self.canal_temporal.delete(reason="Subida finalizada")
        else:
            await interaction.response.send_message("❌ No encontré ese canal.", ephemeral=True)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.data.get("custom_id") == "boton_subida":
        guild = interaction.guild
        autor = interaction.user

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            autor: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True)
        }

        canal = await guild.create_text_channel(
            name=f"subida-de-{autor.name}",
            overwrites=overwrites,
            reason="Subida de archivo por botón"
        )
     
        await canal.send(f"{autor.mention} 📎 Sube aquí tu archivo.\nCuando lo hagas, te mostraré un menú para elegir a qué canal debe ir.")
        await interaction.response.send_message("✅ Canal creado. Revisa la lista de canales.", ephemeral=True)
 
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    # Si el mensaje es en el canal de buzón alejandrino
    if message.channel.name == "buzón_alejandrino" and not message.author.bot:
        admin_channel = discord.utils.get(message.guild.text_channels, name="cartas_recibidas")
        embed = discord.Embed(
            title="📬 Carta enviada al Buzón Alejandrino",
            description=message.content,
            color=discord.Color.dark_gold()
        )
        embed.set_footer(text=f"Enviado por: {message.author.display_name}")
        await admin_channel.send(embed=embed)
        await message.delete()
        await message.channel.send("✅ Tu carta ha sido enviada al Buzón Alejandrino. Gracias por tu aporte.")

    # Si es un canal temporal y se subió un archivo
    if message.channel.name.startswith("subida-de-") and message.attachments:
        adjunto = message.attachments[0]  # solo permitimos uno por mensaje
        es_util = await procesar_pdf_aleatorio(adjunto, message)
        if not es_util:
            await message.channel.delete(reason="Archivo no válido (rechazado por IA)")
            return              
        await message.channel.send(f"{message.author.mention} ✏️ ¿Qué título le damos al archivo? (Escríbelo en el siguiente mensaje)")
       

        def check(m):
            return m.author == message.author and m.channel == message.channel

        try:
            respuesta = await bot.wait_for("message", check=check, timeout=300.0)  # 5 minutos para responder
            titulo = respuesta.content.strip()

            view = MenuCanalesView(message, message.channel, titulo)
            await message.channel.send("📂 ¿A qué canal lo enviamos?", view=view)

        except asyncio.TimeoutError:
            await message.channel.send("⏳ Tiempo agotado. Vuelve a subir el archivo si quieres intentarlo de nuevo.")

    await bot.process_commands(message)


# PROCESAR ARCHIVO
async def procesar_pdf_aleatorio(adjunto, message):
    if not adjunto.filename.endswith('.pdf'):
        await message.channel.send("❌ Solo se permiten archivos PDF.")
        await message.delete()
        return
    nombre_archivo = f"temp_{adjunto.filename}"
    await adjunto.save(nombre_archivo)

    try:
        lector = PdfReader(nombre_archivo)
        total_paginas = len(lector.pages)

        if total_paginas == 0:
            await message.channel.send("❌ El PDF no tiene páginas legibles.")
            await message.delete()
            return

        paginas = random.sample(range(total_paginas), min(10, total_paginas))
        texto = ""

        for i in sorted(paginas):
            try:
                contenido = lector.pages[i].extract_text()
                if contenido:
                    texto += f"\n--- Página {i+1} ---\n{contenido.strip()}\n"
            except Exception as e:
                texto += f"\n[Error leyendo página {i+1}: {e}]\n"


        async def consultar_llama_y_tokens(texto, api_key):
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }

            data = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Eres un experto en análisis de documentos académicos. Tu tarea es determinar si un texto contiene información útil en el ámbito académico. Responde solo con 'sí' o 'no'.\n\n"
                            "El texto puede contener información de diversas disciplinas: biología, física, química, geología, matemáticas, informática, lenguas, literatura, historia, geografía, economía, psicología. No necesitas analizar el contenido en profundidad, solo identificar si es relevante o no para alguna de estas disciplinas.\n\n"                            
                            "No respondas con explicaciones, solo 'sí' o 'no'.\n\n"
                    )
                },
                    {
                        "role": "user",
                        "content": f"Responde solo con: 'sí' o 'no', ¿tiene este texto contenido útil en ámbito académico?\n\n{texto}"
                    }
                ]
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers,
                    json=data
                )

            if response.status_code == 200:
                try:
                    json_data = response.json()
                except Exception as e:
                    print("❌ Error al parsear el JSON:", e)
                    print("📄 Respuesta cruda:", response.text)
                    return "error", 0

                
                                # === Extraer texto generado ===
                texto = json_data["choices"][0]["message"]["content"]
                print("📨 Respuesta del modelo:", texto)

                # === Analizar respuesta ===
                respuesta = texto.strip().lower()

                # === Obtener tokens usados por esta respuesta ===
                usage = response.json().get("usage", {})
               

                try:
                    tokens_usados = usage.get("total_tokens", 0)
                    print("📉 Tokens usados:", tokens_usados)
                except ValueError:
                    print("⚠️ Cabecera malformada o vacía")
                    tokens_usados = 0

                # === Leer tokens totales usados hoy desde archivo ===
                ruta_tokens = "tokens_hoy.txt"
                fecha_actual = datetime.now().strftime("%Y-%m-%d")
                tokens_totales_usados = 0

                if os.path.exists(ruta_tokens):
                    with open(ruta_tokens, "r") as f:
                        datos = f.read().split(",")
                        if len(datos) == 2 and datos[0] == fecha_actual:
                            tokens_totales_usados = int(datos[1])
                        else:
                            tokens_totales_usados = 0  # Nueva fecha, reiniciar contador

                # === Sumar nuevos tokens y guardar ===
                tokens_totales_usados += tokens_usados
                with open(ruta_tokens, "w") as f:
                    f.write(f"{fecha_actual},{tokens_totales_usados}")

                # === Calcular archivos restantes ===
                tokens_restantes = max(100000 - tokens_totales_usados, 0)
                archivos_restantes = tokens_restantes // 7000

                # === Devolver respuesta y archivos restantes ===
                return respuesta, archivos_restantes


            else:
                print("❌ Error HTTP:", response.status_code)
                print("🔎 Contenido crudo:", response.text)
                return "error", 0


        respuesta, archivos_restantes = await consultar_llama_y_tokens(texto, GROQ_API_KEY)
        print("✅ Resultado recibido:", respuesta, archivos_restantes)

        canal = discord.utils.get(bot.get_all_channels(), name="subidas")
        mensaje_id = obtener_id_mensaje(canal.id, "contador")
        print(f"🔍 Obtenido mensaje ID: {mensaje_id} del canal {canal.id}")       
    

        if mensaje_id:
            print(f"🔄 Actualizando mensaje ID: {mensaje_id} en canal {canal.id}")
            try:
                mensaje = await canal.fetch_message(mensaje_id)
                await mensaje.delete()
                print("🗑️ Mensaje anterior eliminado.")
                nuevo_mensaje = await canal.send( f"# 📦 Archivos restantes para subida hoy: {archivos_restantes}")
                guardar_id_mensaje(canal.id, "contador", nuevo_mensaje.id)
                print("✅ Mensaje actualizado con el nuevo conteo de archivos restantes.")

            except discord.NotFound:
                print("⚠️ El mensaje guardado ya no existe en ese canal.")
            except discord.Forbidden:
                print("⛔ No tienes permisos para leer/borrar en ese canal.")
            except discord.HTTPException as e:
                print(f"❌ Error inesperado al intentar borrar el mensaje: {e}")
  

      

        if "sí" in respuesta:
            await message.channel.send("✅ El PDF contiene información útil.")            
            return True
        else:
            await message.channel.send("❌ El PDF no contiene información útil y será eliminado.")
            await message.delete()
            time.sleep(2)  # Espera para que el usuario vea el mensaje
            return False
        
    except Exception as e:
        await message.channel.send("❌ Error al procesar el PDF. Asegúrate de que sea válido.")
        print("Error:", e)

    finally:
        os.remove(nombre_archivo)
       


bot.run(TOKEN)

 

