import time
import threading
import requests
import schedule
from datetime import datetime
from sense_hat import SenseHat
import pygame

pygame.init()

# API og SenseHat indstillinger
API_KEY = "6a0ef35108054010834112455242711"  # API-nøgle til WeatherAPI
CITY = "Roskilde"  # Byen der skal hentes vejrdata for
URL = f"http://api.weatherapi.com/v1/current.json?key={API_KEY}&q={CITY}&aqi=no"  # URL til API

# API til Raspberry Puppy
BASE_URL = "https://raspberrypuppy.azurewebsites.net"

# Function to get data from the API
def get_data(endpoint):
    url = f"{BASE_URL}/{endpoint}"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()

# Function to post data to the API
def post_data(endpoint, data):
    url = f"{BASE_URL}/{endpoint}"
    response = requests.post(url, json=data)
    if response.status_code == 201:
        return response.json()
    else:
        response.raise_for_status()

# Function to update data on the API
def update_data(endpoint, data):
    url = f"{BASE_URL}/{endpoint}"
    response = requests.put(url, json=data)
    if response.status_code == 200:
        return response.json()
    else:
        response.raise_for_status()

# Function to delete data from the API
def delete_data(endpoint):
    url = f"{BASE_URL}/{endpoint}"
    response = requests.delete(url)
    if response.status_code == 204:
        return "Deleted successfully"
    else:
        response.raise_for_status()


sense = SenseHat()
sense.clear()  # Rydder SenseHat LED-skærmen

# Lyde
loud_bark = pygame.mixer.Sound('/home/pi/Loud.wav')  # Høj gø-lyd
quiet_bark = pygame.mixer.Sound('/home/pi/Quiet.mp3')  # Stille gø-lyd
silent_bark = pygame.mixer.Sound('/home/pi/growl.wav')  # Knurren
want_inside_bark = pygame.mixer.Sound('/home/pi/Inside.mp3')  # Lyd for at komme ind

class Dog:
    class SoundSignal:
        SILENT = silent_bark  # Ingen lyd
        LOUD = loud_bark  # Høj lyd
        QUIET = quiet_bark  # Stille lyd
        WANT_INSIDE = want_inside_bark  # Ønske om at komme ind

    def __init__(self, id, name, race):
        self.id = id  # Hundens ID
        self.name = name  # Hundens navn
        self.race = race  # Hundens race
        self.needs_to_walk = False  # Om hunden skal gå
        self.sound_signal = Dog.SoundSignal.SILENT  # Standard lydsignal
        self.is_outside = False  # Om hunden er udenfor
        self.start_time_outside = None  # Tidspunkt for at gå udenfor

    def send_signal(self):
        """Starter signalet for at indikere, at hunden skal ud."""
        self.needs_to_walk = True  # Markér at hunden skal ud
        self._bark_cycle(Dog.SoundSignal.QUIET, (0, 255, 0), 30)  # Stille gøen med grønt lys
        self._bark_cycle(Dog.SoundSignal.LOUD, (255, 0, 0), 300)  # Høj gøen med rødt lys
        self.stop_signal()  # Stop signalet

    def _bark_cycle(self, sound_signal, color, duration):
        """En enkelt cyklus af gøen med specifik lyd og farve."""
        self.sound_signal = sound_signal  # Sæt lydsignal
        sound_signal.play(loops=-1)  # Afspil lyden i loop
        sense.clear(*color)  # Sæt SenseHat LED til farve
        time.sleep(duration)  # Vent i den angivne varighed
        sound_signal.stop()  # Stop lyden

    def stop_sounds(self):
        """Stopper alle mulige lyde."""
        loud_bark.stop()
        quiet_bark.stop()
        silent_bark.stop()
        want_inside_bark.stop()

    def stop_signal(self):
        """Stopper alle lyde og rydder SenseHat LED."""
        self.stop_sounds()  # Stop alle lyde
        sense.clear()  # Ryd LED-skærmen
        self.needs_to_walk = False  # Nulstil behovet for at gå

    def check_outside_status(self):
        """Kontrollerer status for udendørstid og temperatur."""
        indoor_temp = sense.get_temperature()  # Få temperaturen indendørs
        outdoor_temp = self.get_outdoor_temperature()  # Få temperaturen udendørs
        print(f"Hundens temperatur: {indoor_temp:.2f}°C")
        print(f"Udendørs temperatur: {outdoor_temp:.2f}°C")

        if outdoor_temp is None:  # Hvis temperaturen ikke kunne hentes
            print("Kunne ikke hente udendørstemperatur.")
            return

        temp_diff = abs(indoor_temp - outdoor_temp)  # Beregn temperaturforskel
        print(f"Temperaturforskel: {temp_diff:.2f}")

        if temp_diff < 20:  # Hvis temperaturforskellen er mindre end 20 grader
            self.handle_outside()  # Håndter logik for udenfor
        else:
            self.handle_inside()  # Håndter logik for indenfor

    def handle_outside(self):
        """Håndterer logik, når hunden er udenfor."""
        if not self.is_outside:  # Hvis hunden ikke allerede er udenfor
            self.is_outside = True
            self.start_time_outside = time.time()  # Registrér starttidspunktet
            print("Hunden er udenfor.")
            self.stop_sounds()  # Stop alle lyde
            sense.clear(0, 0, 255)  # Blå lys

        self.elapsed_time_outside = time.time() - self.start_time_outside  # Tid brugt udenfor
        print(f"Hunden har været udenfor i {self.elapsed_time_outside:.2f} sekunder.")  # Udskriv tid udenfor

        if self.elapsed_time_outside > 100:  # Hvis hunden har været ude længe nok
            print("Hunden har været ude længe nok.")
            want_inside_bark.play()  # Spil lyd for at komme ind
            sense.clear(255, 255, 0)  # Gul lys
            final_time_outside = print(f"Hunden har været udenfor i alt {self.elapsed_time_outside:.2f} sekunder.")
            time.sleep(7)  # Vent lidt tid
            self.stop_signal()  # Stop signalet

    def too_fast_inside(self):
        """Håndterer logik, når hunden er kommet ind for hurtigt."""
        if self.is_outside and self.elapsed_time_outside < 100 and not self.needs_to_walk:  
            # Hvis hunden har været udenfor i mindre end 100 sekunder og er kommet ind:
            print("Hunden kom hurtigt ind.")
            loud_bark.play()  # Høj gøen lyd
            sense.clear(255, 0, 0)  # Rød lys
            self.stop_signal()  # Stop signalet
        
    def handle_inside(self):
        """Håndterer logik, når hunden er indenfor."""
        if self.is_outside:  # Hvis hunden er udenfor
            print("Hunden er nu indenfor.")
            self.is_outside = False
            self.start_time_outside = None  # Nulstil starttidspunkt
            self.too_fast_inside()  # Tjek om hunden kom hurtigt ind
            self.stop_signal()  # Stop signalet

    @staticmethod
    def get_outdoor_temperature():
        """Henter udendørstemperaturen fra API."""
        try:
            response = requests.get(URL)  # Send API-forespørgsel
            response.raise_for_status()  # Tjek for fejl
            data = response.json()  # Parse JSON-svar
            # Hent relevante data
            location = data['location']['name']
            country = data['location']['country']
            current_temp = data['current']['temp_c']
            last_updated = data['current']['last_updated']
            
            # Print de relevante oplysninger
            print(f"Tid: {last_updated}")
            print(f"Lokation: {location}, {country}")
            print(f"Temperatur: {current_temp:.2f}°C") 


            return data['current']['temp_c']  # Returnér temperaturen
        except requests.RequestException as e:
            print(f"API-fejl: {e}")  # Log API-fejl
            return None

# Opret en hund
my_dog = Dog(1, "Lilo", "Golden Retriever")  # Hundens ID, navn og race

# Planlæg signaler
schedule.every().day.at("08:00:00").do(my_dog.send_signal)  # Signal kl. 08:00
schedule.every().day.at("16:00:00").do(my_dog.send_signal)  # Signal kl. 16:00
schedule.every().day.at("22:00:00").do(my_dog.send_signal)  # Signal kl. 22:00

# Test tidspunkt
schedule.every().day.at("10:41:00").do(my_dog.send_signal)  

# Baggrundstråd for temperaturkontrol
def monitor_temperature():
    while True:
        my_dog.check_outside_status()  # Tjek status for hunden
        time.sleep(5)  # Vent 5 sekunder med at printe ud i terminalen

threading.Thread(target=monitor_temperature, daemon=True).start()  # Start tråd

# Kør planlagt handling
while True:
    schedule.run_pending()  # Udfør planlagte opgaver
    time.sleep(1)  # Vent 1 sekund
