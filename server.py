import socket
import threading
import time
from sys import argv
import logging

logging.basicConfig(level=logging.DEBUG,
	format='[%(asctime)s] %(levelname)s: %(message)s',
	datefmt='%Y-%m-%d %H:%M:%S',
	filename='ttt_server.log');
console = logging.StreamHandler();
console.setLevel(logging.INFO);
logging.getLogger('').addHandler(console);

class TTTServer:
	def __init__(self):
		self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM);
	def bind(self, port_number):
		while True:
			try:
				self.server_socket.bind(("", int(port_number)));
				logging.info("Reserved port " + str(port_number));
				self.server_socket.listen(1);
				logging.info("Listening to port " + str(port_number));
				break;
			except:
				logging.warning("There is an error when trying to bind " + 
					str(port_number));
				choice = input("[A]bort, [C]hange port, or [R]etry?");
				if(choice.lower() == "a"):
					exit();
				elif(choice.lower() == "c"):
					port_number = input("Please enter the port:");
	def close(self):
		self.server_socket.close();
class TTTServerGame(TTTServer):
	def __init__(self):
		TTTServer.__init__(self);

	def start(self):
		self.waiting_players = [];
		self.lock_matching = threading.Lock();
		self.__main_loop();

	def __main_loop(self):
		while True:
			connection, client_address = self.server_socket.accept();
			logging.info("Received connection from " + str(client_address));

			new_player = Player(connection);
			self.waiting_players.append(new_player);

			try:
				threading.Thread(target=self.__client_thread, 
					args=(new_player,)).start();
			except:
				logging.error("Failed to create thread.");

	def __client_thread(self, player):
		try:
			player.send("A", str(player.id));
			if(player.recv(2, "c") != "1"):
				logging.warning("Client " + str(player.id) + 
					" didn't confirm the initial message.");
				return;

			while player.is_waiting:
				match_result = self.matching_player(player);

				if(match_result is None):
					time.sleep(1);
					player.check_connection();
				else:
					new_game = Game();
					new_game.player1 = player;
					new_game.player2 = match_result;
					new_game.board_content = list("         ");

					try:
						new_game.start();
					except:
						logging.warning("Game between " + str(new_game.player1.id) + 
							" and " + str(new_game.player2.id) + 
							" is finished unexpectedly.");
					return;
		except:
			print("Player " + str(player.id) + " disconnected.");
		finally:
			self.waiting_players.remove(player);

	def matching_player(self, player):
		self.lock_matching.acquire();
		try:
			for p in self.waiting_players:
				if(p.is_waiting and p is not player):
					player.match = p;
					p.match = player;
					player.role = "X";
					p.role = "O";
					player.is_waiting = False;
					p.is_waiting = False;
					return p;
		finally:
			self.lock_matching.release();
		return None;

class Player:
	count = 0;

	def __init__(self, connection):
		Player.count = Player.count + 1
		self.id = Player.count;
		self.connection = connection;
		self.is_waiting = True;	

	def send(self, command_type, msg):
		try:
			self.connection.send((command_type + msg).encode());
		except:
			self.__connection_lost();

	def recv(self, size, expected_type):
		try:
			msg = self.connection.recv(size).decode();
			if(msg[0] == "q"):
				logging.info(msg[1:]);
				self.__connection_lost();
			elif(msg[0] != expected_type):
				self.__connection_lost();
			elif(msg[0] == "i"):
				return int(msg[1:]);
			else:
				return msg[1:];
			return msg;
		except:
			self.__connection_lost();
		return None;

	def check_connection(self):
		self.send("E", "z");
		if(self.recv(2, "e") != "z"):
			self.__connection_lost();

	def send_match_info(self):
		self.send("R", self.role);
		if(self.recv(2,"c") != "2"):
			self.__connection_lost();
		self.send("I", str(self.match.id));
		if(self.recv(2,"c") != "3"):
			self.__connection_lost();

	def __connection_lost(self):
		logging.warning("Player " + str(self.id) + " connection lost.");
		try:
			self.match.send("Q", "The other player has lost connection" + 
				" with the server.\nGame over.");
		except:
			pass;
		raise Exception;

class Game:
	def start(self):
		self.player1.send_match_info();
		self.player2.send_match_info();

		logging.info("Player " + str(self.player1.id) + 
			" is matched with player " + str(self.player2.id));

		while True:
			if(self.move(self.player1, self.player2)):
				return;
			if(self.move(self.player2, self.player1)):
				return;

	def move(self, moving_player, waiting_player):
		moving_player.send("B", ("".join(self.board_content)));
		waiting_player.send("B", ("".join(self.board_content)));
		moving_player.send("C", "Y");
		waiting_player.send("C", "N");
		move = int(moving_player.recv(2, "i"));
		waiting_player.send("I", str(move));
		if(self.board_content[move - 1] == " "):
		 	self.board_content[move - 1] = moving_player.role;
		else:
			logging.warning("Player " + str(moving_player.id) + 
				" is attempting to take a position that's already " + 
				"been taken.");

		result, winning_path = self.check_winner(moving_player);
		if(result >= 0):
			moving_player.send("B", ("".join(self.board_content)));
			waiting_player.send("B", ("".join(self.board_content)));

			if(result == 0):
				moving_player.send("C", "D");
				waiting_player.send("C", "D");
				print("Game between player " + str(self.player1.id) + " and player " 
					+ str(self.player2.id) + " ends with a draw.");
				return True;
			if(result == 1):
				moving_player.send("C", "W");
				waiting_player.send("C", "L");
				moving_player.send("P", winning_path);
				waiting_player.send("P", winning_path);
				print("Player " + str(self.player1.id) + " beats player " 
					+ str(self.player2.id) + " and finishes the game.");
				return True;
			return False;

	def check_winner(self, player):
		s = self.board_content;

		if(len(set([s[0], s[1], s[2], player.role])) == 1):
			return 1, "012";
		if(len(set([s[3], s[4], s[5], player.role])) == 1):
			return 1, "345";
		if(len(set([s[6], s[7], s[8], player.role])) == 1):
			return 1, "678";

		if(len(set([s[0], s[3], s[6], player.role])) == 1):
			return 1, "036";
		if(len(set([s[1], s[4], s[7], player.role])) == 1):
			return 1, "147";
		if(len(set([s[2], s[5], s[8], player.role])) == 1):
			return 1, "258";

		if(len(set([s[0], s[4], s[8], player.role])) == 1):
			return 1, "048";
		if(len(set([s[2], s[4], s[6], player.role])) == 1):
			return 1, "246";
		if " " not in s:
			return 0, "";
		return -1, "";

def main():
	if(len(argv) >= 2):
		port_number = argv[1];
	else:
		port_number = input("Please enter the port:");

	try:
		server = TTTServerGame();
		server.bind(port_number);
		server.start();
		server.close();
	except BaseException as e:
		logging.critical("Server critical failure.\n" + str(e));

if __name__ == "__main__":
	main();
