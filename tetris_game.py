import pygame
import random
import sys

# 初始化 pygame
pygame.init()

# 游戏常量
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
BLOCK_SIZE = 30
GRID_WIDTH = 20
GRID_HEIGHT = 20
FPS = 60

# 颜色定义
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GRAY = (128, 128, 128)
COLORS = [
    (0, 255, 255),   # 青色 - I 形
    (255, 255, 0),   # 黄色 - O 形
    (255, 0, 255),   # 紫色 - T 形
    (0, 255, 0),     # 绿色 - S 形
    (255, 165, 0),   # 橙色 - Z 形
    (0, 0, 255),     # 蓝色 - J 形
    (128, 0, 128)    # 深紫 - L 形
]

# 方块形状定义
SHAPES = [
    # I 形
    [
        [1, 1, 1, 1]
    ],
    # O 形
    [
        [1, 1],
        [1, 1]
    ],
    # T 形
    [
        [0, 1, 0],
        [1, 1, 1],
        [0, 1, 0]
    ],
    # S 形
    [
        [0, 1, 1],
        [1, 1, 0],
        [0, 0, 0]
    ],
    # Z 形
    [
        [1, 1, 0],
        [0, 1, 1],
        [0, 0, 0]
    ],
    # J 形
    [
        [1, 0, 0],
        [1, 1, 1],
        [0, 0, 0]
    ],
    # L 形
    [
        [0, 0, 1],
        [1, 1, 1],
        [0, 0, 0]
    ]
]

class Tetromino:
    """方块类"""
    def __init__(self, x, y, shape_index):
        self.x = x
        self.y = y
        self.shape_index = shape_index
        self.shape = SHAPES[shape_index]
        self.color = COLORS[shape_index]
        self.rotation = 0
        
    def get_blocks(self):
        """获取方块的所有块位置"""
        blocks = []
        for row_idx, row in enumerate(self.shape):
            for col_idx, cell in enumerate(row):
                if cell:
                    blocks.append((self.x + col_idx, self.y + row_idx))
        return blocks
    
    def rotate(self, direction=1):
        """旋转方块"""
        self.rotation = (self.rotation + direction) % 4
        new_shape = self.shape
        for _ in range(direction):
            new_shape = [list(row) for row in zip(*new_shape[::-1])]
        self.shape = new_shape
    
    def move(self, dx, dy):
        """移动方块"""
        self.x += dx
        self.y += dy
        
    def is_valid_position(self, grid):
        """检查方块位置是否有效"""
        blocks = self.get_blocks()
        for x, y in blocks:
            if x < 0 or x >= GRID_WIDTH or y >= GRID_HEIGHT:
                return False
            if grid[y][x] != 0:
                return False
        return True

class TetrisGame:
    """俄罗斯方块游戏类"""
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("🎮 俄罗斯方块 - LySoY 专属")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)
        
        self.reset_game()
        
    def reset_game(self):
        """重置游戏状态"""
        self.grid = [[0 for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        self.score = 0
        self.level = 1
        self.lines_cleared = 0
        self.game_over = False
        self.paused = False
        
        # 生成第一个方块
        self.current_piece = self.spawn_piece()
        self.next_piece = self.spawn_piece()
        
        # 游戏计时
        self.drop_time = 0
        self.drop_interval = 1000  # 毫秒
        
    def spawn_piece(self):
        """生成新方块"""
        shape_index = random.randint(0, len(SHAPES) - 1)
        x = GRID_WIDTH // 2 - 2
        y = -2
        return Tetromino(x, y, shape_index)
    
    def draw_grid(self):
        """绘制游戏网格"""
        # 绘制背景
        self.screen.fill(BLACK)
        
        # 绘制游戏区域
        pygame.draw.rect(self.screen, GRAY, 
                        (50, 50, GRID_WIDTH * BLOCK_SIZE, GRID_HEIGHT * BLOCK_SIZE), 2)
        
        # 绘制网格线
        for x in range(50, 50 + GRID_WIDTH * BLOCK_SIZE, BLOCK_SIZE):
            pygame.draw.line(self.screen, GRAY, (x, 50), (x, 50 + GRID_HEIGHT * BLOCK_SIZE))
        for y in range(50, 50 + GRID_HEIGHT * BLOCK_SIZE, BLOCK_SIZE):
            pygame.draw.line(self.screen, GRAY, (50, y), (50 + GRID_WIDTH * BLOCK_SIZE, y))
    
    def draw_board(self):
        """绘制游戏板和已放置的方块"""
        for row in range(GRID_HEIGHT):
            for col in range(GRID_WIDTH):
                if self.grid[row][col] != 0:
                    color_index = self.grid[row][col] - 1
                    color = COLORS[color_index]
                    x = 50 + col * BLOCK_SIZE
                    y = 50 + row * BLOCK_SIZE
                    pygame.draw.rect(self.screen, color, (x, y, BLOCK_SIZE, BLOCK_SIZE))
                    # 添加边框效果
                    pygame.draw.rect(self.screen, WHITE, (x, y, BLOCK_SIZE, BLOCK_SIZE), 2)
    
    def draw_piece(self, piece):
        """绘制当前方块"""
        blocks = piece.get_blocks()
        for x, y in blocks:
            color = piece.color
            rect_x = 50 + x * BLOCK_SIZE
            rect_y = 50 + y * BLOCK_SIZE
            pygame.draw.rect(self.screen, color, (rect_x, rect_y, BLOCK_SIZE, BLOCK_SIZE))
            pygame.draw.rect(self.screen, WHITE, (rect_x, rect_y,BLOCK_SIZE, BLOCK_SIZE), 2)
    
    def draw_ui(self):
        """绘制用户界面"""
        # 分数
        score_text = self.font.render(f"分数：{self.score}", True, WHITE)
        self.screen.blit(score_text, (600, 60))
        
        # 等级
        level_text = self.font.render(f"等级：{self.level}", True, WHITE)
        self.screen.blit(level_text, (600, 120))
        
        # 消除行数
        lines_text = self.font.render(f"消除行数：{self.lines_cleared}", True, WHITE)
        self.screen.blit(lines_text, (600, 180))
        
        # 下一个方块
        next_text = self.font.render("下一个方块", True, WHITE)
        self.screen.blit(next_text, (600, 260))
        
        # 绘制下一个方块
        next_x = 600
        next_y = 320
        for row_idx, row in enumerate(self.next_piece.shape):
            for col_idx, cell in enumerate(row):
                if cell:
                    color = self.next_piece.color
                    rect_x = next_x + col_idx * BLOCK_SIZE
                    rect_y = next_y + row_idx * BLOCK_SIZE
                    pygame.draw.rect(self.screen, color, (rect_x, rect_y, BLOCK_SIZE, BLOCK_SIZE))
                    pygame.draw.rect(self.screen, WHITE, (rect_x, rect_y, BLOCK_SIZE, BLOCK_SIZE), 2)
        
        # 游戏状态
        if self.game_over:
            # 绘制游戏结束背景
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 180))
            self.screen.blit(overlay, (0, 0))
            
            # 游戏结束文字
            game_over_text = self.font.render("🎉 游戏结束 🎉", True, (255, 255, 0))
            restart_text = self.small_font.render("按 R 重新开始", True, WHITE)
            quit_text = self.small_font.render("按 Q 退出游戏", True, WHITE)
            
            self.screen.blit(game_over_text, (SCREEN_WIDTH // 2 - 120, SCREEN_HEIGHT // 2 - 60))
            self.screen.blit(restart_text, (SCREEN_WIDTH // 2 - 80, SCREEN_HEIGHT // 2 + 20))
            self.screen.blit(quit_text, (SCREEN_WIDTH // 2 - 80,SCREEN_HEIGHT // 2 + 60))
        elif self.paused:
            # 绘制暂停背景
            overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 120))
            self.screen.blit(overlay, (0, 0))
            
            # 暂停文字
            pause_text = self.font.render("⏸️ 游戏暂停 ⏸️", True, (255, 255, 0))
            resume_text = self.small_font.render("按 P 继续游戏", True, WHITE)
            
            self.screen.blit(pause_text, (SCREEN_WIDTH // 2 - 120, SCREEN_HEIGHT // 2 - 60))
            self.screen.blit(resume_text, (SCREEN_WIDTH // 2 - 80,SCREEN_HEIGHT // 2 + 40))
    
    def check_collision(self, piece):
        """检查方块碰撞"""
        return piece.is_valid_position(self.grid)
    
    def lock_piece(self):
        """锁定当前方块"""
        blocks = self.current_piece.get_blocks()
        for x, y in blocks:
            self.grid[y][x] = self.current_piece.shape_index + 1
        
        # 检查消除行
        self.clear_lines()
        
        # 检查游戏结束
        if not self.check_game_over():
            # 生成新方块
            self.current_piece = self.next_piece
            self.next_piece = self.spawn_piece()
            
            # 检查新方块是否能放置
            if not self.check_collision(self.current_piece):
                self.game_over = True
    
    def clear_lines(self):
        """消除满行"""
        lines_to_remove = []
        for row in range(GRID_HEIGHT):
            if all(self.grid[row]):
                lines_to_remove.append(row)
        
        if lines_to_remove:
            # 从网格中移除满行
            for row in lines_to_remove:
                del self.grid[row]
                # 在顶部添加新行
                self.grid.insert(0, [0 for _ in range(GRID_WIDTH)])
            
            # 计算消除行数
            num_lines = len(lines_to_remove)
            self.lines_cleared += num_lines
            
            # 根据消除行数计算分数
            points = [0, 100, 300, 500, 800]
            self.score += points[min(num_lines, 4)] * self.level
            
            # 升级
            if self.lines_cleared % 10 == 0:
                self.level += 1
                self.drop_interval = max(100, 1000 - (self.level - 1) * 100)
    
    def check_game_over(self):
        """检查游戏是否结束"""
        # 检查顶部是否有可放置的位置
        for col in range(GRID_WIDTH):
            if self.grid[0][col] == 0:
                return True
        return False
    
    def handle_events(self):
        """处理用户事件"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                
                if self.game_over:
                    if event.key == pygame.K_r:
                        self.reset_game()
                    elif event.key == pygame.K_q:
                        return False
                else:
                    if event.key == pygame.K_p:
                        self.paused = not self.paused
                    elif not self.paused:
                        if event.key == pygame.K_LEFT:
                            self.current_piece.move(-1, 0)
                        elif event.key == pygame.K_RIGHT:
                            self.current_piece.move(1, 0)
                        elif event.key == pygame.K_DOWN:
                            self.current_piece.move(0, 1)
                        elif event.key == pygame.K_UP:
                            self.current_piece.rotate(1)
                        elif event.key == pygame.K_SPACE:
                            # 硬降落
                            while self.current_piece.move(0, 1):
                                pass
                            self.lock_piece()
        
        return True
    
    def update(self):
        """更新游戏状态"""
        if not self.game_over and not self.paused:
            # 根据时间间隔更新方块位置
            current_time = pygame.time.get_ticks()
            if current_time - self.drop_time > self.drop_interval:
                if self.current_piece.move(0, 1):
                    self.drop_time = current_time
                else:
                    # 无法继续下落，锁定方块
                    self.current_piece.move(0, -1)
                    self.lock_piece()
    
    def run(self):
        """运行游戏主循环"""
        running = True
        
        while running:
            # 处理事件
            running = self.handle_events()
            
            # 更新游戏状态
            self.update()
            
            # 绘制游戏
            self.draw_grid()
            self.draw_board()
            self.draw_piece(self.current_piece)
            self.draw_ui()
            
            # 更新显示
            pygame.display.flip()
            
            # 控制帧率
            self.clock.tick(FPS)
        
        pygame.quit()
        sys.exit()

def main():
    """主函数"""
    print("🎮 正在启动俄罗斯方块游戏...")
    print("📋 操作说明:")
    print("  ← → : 左右移动方块")
    print("  ↑ : 旋转方块")
    print("  ↓ : 加速下落")
    print("  空格 : 立即降落")
    print("  P : 暂停/继续游戏")
    print("  R : 重新开始游戏")
    print("  Q/ESC : 退出游戏")
    print("\n祝游戏愉快！🎵")
    
    game = TetrisGame()
    game.run()

if __name__ == "__main__":
    main()