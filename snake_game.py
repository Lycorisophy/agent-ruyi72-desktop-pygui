# snake_game.py
import pygame
import random
import sys

# 初始化 Pygame
pygame.init()

# 游戏常量
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
GRID_SIZE = 20
FPS = 10

# 颜色定义
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
DARK_GREEN = (0, 128, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)

# 蛇的颜色渐变
SNAKE_COLORS = [
    (0, 128, 0),    # 深绿
    (0, 200, 0),    # 中绿
    (100, 255, 100),# 浅绿
    (150, 255, 150)# 嫩绿
]

class Snake:
    def __init__(self):
        self.reset()
    
    def reset(self):
        """重置蛇的状态"""
        self.body = [(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)]
        self.direction = (1, 0)  # 初始向右移动
        self.score = 0
        self.level = 1
        self.color_index = 0
    
    def move(self):
        """移动蛇身"""
        head_x, head_y = self.body[0]
        dir_x, dir_y = self.direction
        new_head = (head_x + dir_x * GRID_SIZE, head_y + dir_y * GRID_SIZE)
        
        # 将新头部添加到蛇身前端
        self.body.insert(0, new_head)
        
        # 移除尾部（如果蛇没有吃到食物）
        if len(self.body) > self.score + 1:
            self.body.pop()
    
    def grow(self):
        """蛇身增长"""
        self.score += 1
        # 每 5 分提升一级
        if self.score % 5 == 0:
            self.level += 1
            self.color_index = (self.color_index + 1) % len(SNAKE_COLORS)
    
    def get_head(self):
        """获取蛇头坐标"""
        return self.body[0]
    
    def check_collision(self):
        """检测蛇与自身或墙壁的碰撞"""
        head = self.get_head()
        
        # 检测墙壁碰撞
        if (head[0] < 0 or head[0] >= SCREEN_WIDTH or 
            head[1] < 0 or head[1] >= SCREEN_HEIGHT):
            return True
        
        # 检测自身碰撞
        if head in self.body[1:]:
            return True
        
        return False
    
    def get_color(self):
        """获取当前蛇身颜色"""
        return SNAKE_COLORS[self.color_index]

class Food:
    def __init__(self):
        self.position = (0, 0)
        self.color = RED
    
    def spawn(self, snake_body):
        """在随机位置生成食物"""
        while True:
            x = random.randint(0, (SCREEN_WIDTH // GRID_SIZE) - 1) * GRID_SIZE
            y = random.randint(0, (SCREEN_HEIGHT // GRID_SIZE) - 1) * GRID_SIZE
            if (x, y) not in snake_body:
                self.position = (x, y)
                break
    
    def draw(self, screen):
        """绘制食物"""
        pygame.draw.circle(screen, self.color, self.position, GRID_SIZE // 2)

class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("🐍 贪吃蛇游戏 - LySoY 专属")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.snake = Snake()
        self.food = Food()
        self.game_over = False
        self.paused = False
    
    def handle_events(self):
        """处理用户事件"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                
                if event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                
                if not self.paused and not self.game_over:
                    if event.key == pygame.K_UP and self.snake.direction[1] != 1:
                        self.snake.direction = (0, -1)
                    elif event.key == pygame.K_DOWN and self.snake.direction[1] != -1:
                        self.snake.direction = (0, 1)
                    elif event.key == pygame.K_LEFT and self.snake.direction[0] != 1:
                        self.snake.direction = (-1, 0)
                    elif event.key == pygame.K_RIGHT and self.snake.direction[0] != -1:
                        self.snake.direction = (1, 0)
        
        return True
    
    def update(self):
        """更新游戏状态"""
        if self.paused or self.game_over:
            return
        
        self.snake.move()
        
        # 检测食物碰撞
        head = self.snake.get_head()
        if head == self.food.position:
            self.snake.grow()
            self.food.spawn(self.snake.body)
        
        # 检测游戏结束
        if self.snake.check_collision():
            self.game_over = True
    
    def draw_grid(self):
        """绘制网格背景"""
        for x in range(0, SCREEN_WIDTH, GRID_SIZE):
            for y in range(0, SCREEN_HEIGHT, GRID_SIZE):
                rect = pygame.Rect(x, y, GRID_SIZE, GRID_SIZE)
                pygame.draw.rect(self.screen, (240, 240, 240), rect, 1)
    
    def draw_ui(self):
        """绘制用户界面"""
        # 绘制分数
        score_text = self.font.render(f"分数：{self.snake.score}", True, BLACK)
        level_text = self.font.render(f"等级：{self.snake.level}", True, BLACK)
        self.screen.blit(score_text, (20, 20))
        self.screen.blit(level_text, (20, 60))
        
        # 绘制控制说明
        controls_text = self.font.render("操作：方向键移动 | 空格暂停 | ESC 退出", True, BLUE)
        self.screen.blit(controls_text, (SCREEN_WIDTH - 400, 20))
        
        # 游戏结束提示
        if self.game_over:
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
            overlay.set_alpha(128)
            overlay.fill(BLACK)
            self.screen.blit(overlay, (0, 0))
            
            game_over_text = self.font.render("🎉 游戏结束!", True, YELLOW)
            restart_text = self.font.render("按 R 重新开始 | 按 ESC 退出", True, WHITE)
            self.screen.blit(game_over_text, (SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 30))
            self.screen.blit(restart_text, (SCREEN_WIDTH // 2 - 120, SCREEN_HEIGHT // 2 + 20))
        
        # 暂停提示
        if self.paused:
            pause_text = self.font.render("⏸️ 游戏暂停", True, GREEN)
            self.screen.blit(pause_text, (SCREEN_WIDTH // 2 - 60, SCREEN_HEIGHT // 2))
    
    def draw(self):
        """绘制游戏画面"""
        self.screen.fill(WHITE)
        self.draw_grid()
        
        # 绘制蛇身
        for i, segment in enumerate(self.snake.body):
            color = SNAKE_COLORS[(self.snake.color_index + i) % len(SNAKE_COLORS)]
            pygame.draw.rect(self.screen, color, 
                           pygame.Rect(segment[0], segment[1], GRID_SIZE, GRID_SIZE))
            # 绘制蛇身轮廓
            pygame.draw.rect(self.screen, BLACK, 
                           pygame.Rect(segment[0], segment[1], GRID_SIZE, GRID_SIZE), 1)
        
        # 绘制食物
        self.food.draw(self.screen)
        
        # 绘制用户界面
        self.draw_ui()
        
        pygame.display.flip()
    
    def run(self):
        """游戏主循环"""
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(FPS)
        
        # 游戏结束后的处理
        if self.game_over:
            while True:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_r:
                            self.snake.reset()
                            self.game_over = False
                            self.food.spawn(self.snake.body)
                            return
                        elif event.key == pygame.K_ESCAPE:
                            return
        
        pygame.quit()
        sys.exit()

def main():
    """游戏入口"""
    game = Game()
    game.run()

if __name__ == "__main__":
    main()