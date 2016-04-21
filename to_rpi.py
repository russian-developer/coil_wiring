import RPi.GPIO as gpio
import threading
import argparse
import time
import sys
import logging
import tty
import termios

logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# ###
# # Config
# ###

GPIO_MODE = gpio.BCM
GPIO_DIRECTION = 14
GPIO_STEP = 15
GPIO_EN_STEPPER = 25
GPIO_OPT1 = 4
GPIO_OPT2 = 11
DISTANCE_PER_STEP = 20 # in microns *1000

###
# /Config
###

lock = threading.Lock()
MAIN_SHAFT_TURN = 0
STEPS = 0
TOTAL_STEPS = 0
DIRECTION = True # True - right; False - left
RUN = True
TRACK = False


class DirectionTracker(threading.Thread):
	def run(self):
		logger.info('DirectionTracker is started')
		global MAIN_SHAFT_TURN, TOTAL_STEPS, TRACK
		_opt1 = _opt2 = False

		while RUN:
			if not TRACK:
				time.sleep(0.1)
				continue
			opt1 = not gpio.input(GPIO_OPT1)
			opt2 = not gpio.input(GPIO_OPT2)
			if _opt1 and _opt2:
				with lock:
					if not opt1:
						MAIN_SHAFT_TURN += 1
						logger.info('Turn +1')
						if MAIN_SHAFT_TURN > 0:
							TOTAL_STEPS += 1
							logger.info('Total steps is %s' % TOTAL_STEPS)
					if not opt2:
						MAIN_SHAFT_TURN -= 1
						logger.info('Turn -1')
			_opt1 = opt1
			_opt2 = opt2
			time.sleep(0.01)


class Stepper(threading.Thread):
	def __init__(self, wire, length):
		super(Stepper, self).__init__()
		self.wire = wire * 1000 # to microns
		self.length = length * 1000 # to microns
		self.coils_per_layer = int(self.length / self.wire)
		self.coils_on_current_layer = 0
		self.remainder = float(0)

	def run(self):
		logger.info('Stepper is started')
		global RUN, DISTANCE_PER_STEP, MAIN_SHAFT_TURN, DIRECTION, STEPS
		while RUN:
			for i in range(0, MAIN_SHAFT_TURN):
				MAIN_SHAFT_TURN = 0
				# Set direction
				if self.coils_on_current_layer >= self.coils_per_layer:
					DIRECTION = not DIRECTION
					gpio.output(GPIO_DIRECTION, DIRECTION)

				# calculate steps
				_steps = self.wire * DISTANCE_PER_STEP + self.remainder
				self.remainder = float(int(_steps) % _steps)

				# make steps
				gpio.output(GPIO_EN_STEPPER, False)
				for i in range(0, int(_steps)):
				    gpio.output(GPIO_STEP, True)
				    gpio.output(GPIO_STEP, False)
				    time.sleep(0.1)
				gpio.output(GPIO_EN_STEPPER, True)
			time.sleep(0.1)


class KeyBoard(threading.Thread):
	def run(self):
		logger.info('KeyBoard is started')
		global TRACK, RUN
		while RUN:
			fd = sys.stdin.fileno()
			old_settings = termios.tcgetattr(fd)
			try:
				tty.setraw(sys.stdin.fileno())
				ch = sys.stdin.read(1)
			finally:
				termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

			if ch in ['a', 'd']: # <- / ->
				gpio.output(GPIO_DIRECTION, ch == 'a' and True or False)
				gpio.output(GPIO_EN_STEPPER, False)
				gpio.output(GPIO_STEP, True)
				gpio.output(GPIO_STEP, False)
				gpio.output(GPIO_EN_STEPPER, True)
			if ch == 's': # start/stop tracker
				TRACK = not TRACK	
				logger.info('Track is %s' % TRACK) 
			if ch == 'q': # exit
				RUN = False
				logger.info('Exit')
				sys.exit()
			time.sleep(0.1)


def gpio_setup():
	gpio.setwarnings(False) 
	gpio.setmode(GPIO_MODE)
	gpio.setup(GPIO_DIRECTION, gpio.OUT)
	gpio.setup(GPIO_STEP, gpio.OUT)
	gpio.setup(GPIO_EN_STEPPER, gpio.OUT)
	gpio.output(GPIO_EN_STEPPER, True)
	gpio.setup(GPIO_OPT1, gpio.IN)
	gpio.setup(GPIO_OPT2, gpio.IN)


if __name__ == '__main__':
	parser = argparse.ArgumentParser()
	parser.add_argument('--wire', type=float, help='Wire diametr in MM', required=True)
	parser.add_argument('--length', type=float, help='Coil length in MM', required=True)
	args = parser.parse_args()
	gpio_setup()
	DirectionTracker().start()
	Stepper(args.wire, args.length).start()
	KeyBoard().start()
	sys.exit()
	