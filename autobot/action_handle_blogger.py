from functools import partial

from insomniac.device_facade import DeviceFacade
from insomniac.interaction import interact_with_user, is_follow_limit_reached_for_source
from insomniac.navigation import search_for
from insomniac.scroll_end_detector import ScrollEndDetector
from insomniac.storage import FollowingStatus
from insomniac.utils import *
import time
import random

import base64
import zlib

FOLLOWERS_BUTTON_ID_REGEX = 'com.instagram.android:id/row_profile_header_followers_container' \
                            '|com.instagram.android:id/row_profile_header_container_followers'


red = "\033[91m"
end = "\033[00m"
blue = "\033[34m"
yellow = "\033[93m"
light_blue = '\033[96m'
purple = '\033[35m'
blue="\033[34m"



def handle_blogger(device,
                   username,
                   session_state,
                   likes_count,
                   follow_percentage,
                   follow_limit,
                   storage,
                   profile_filter,
                   on_like,
                   on_interaction):
    is_myself = username == session_state.my_username
    interaction = partial(interact_with_user,
                          my_username=session_state.my_username,
                          likes_count=likes_count,
                          follow_percentage=follow_percentage,
                          on_like=on_like,
                          profile_filter=profile_filter)
    is_follow_limit_reached = partial(is_follow_limit_reached_for_source,
                                      session_state=session_state,
                                      follow_limit=follow_limit,
                                      source=username)

    if not _open_user_followers(device, username):
        return
    if is_myself:
        _scroll_to_bottom(device)
    # _iterate_over_followers(device, interaction, is_follow_limit_reached, storage, on_interaction, is_myself)
    _iterate_over_comments(device, interaction, is_follow_limit_reached, storage, on_interaction, is_myself)


def _open_user_followers(device, username):
    if username is None:
        print("Open your followers")
        followers_button = device.find(resourceIdMatches=FOLLOWERS_BUTTON_ID_REGEX)
        followers_button.click()
    else:
        if not search_for(device, username=username):
            return False

        print("Open @" + username + " followers")
        followers_button = device.find(resourceIdMatches=FOLLOWERS_BUTTON_ID_REGEX)
        followers_button.click()

    return True


def _scroll_to_bottom(device):
    print("Scroll to bottom")

    def is_end_reached():
        see_all_button = device.find(resourceId='com.instagram.android:id/see_all_button',
                                     className='android.widget.TextView')
        return see_all_button.exists()

    list_view = device.find(resourceId='android:id/list',
                            className='android.widget.ListView')
    while not is_end_reached():
        list_view.swipe(DeviceFacade.Direction.BOTTOM)

    print("Scroll back to the first follower")

    def is_at_least_one_follower():
        follower = device.find(resourceId='com.instagram.android:id/follow_list_container',
                               className='android.widget.LinearLayout')
        return follower.exists()

    while not is_at_least_one_follower():
        list_view.scroll(DeviceFacade.Direction.TOP)


def _iterate_over_followers(device, interaction, is_follow_limit_reached, storage, on_interaction, is_myself):
    # Wait until list is rendered
    device.find(resourceId='com.instagram.android:id/follow_list_container',
                className='android.widget.LinearLayout').wait()

    def scrolled_to_top():
        row_search = device.find(resourceId='com.instagram.android:id/row_search_edit_text',
                                 className='android.widget.EditText')
        return row_search.exists()

    scroll_end_detector = ScrollEndDetector()
    while True:
        print("Iterate over visible followers")
        random_sleep()
        screen_iterated_followers = []
        screen_skipped_followers_count = 0
        scroll_end_detector.notify_new_page()

        try:
            for item in device.find(resourceId='com.instagram.android:id/follow_list_container',
                                    className='android.widget.LinearLayout'):
                user_info_view = item.child(index=1)
                user_name_view = user_info_view.child(index=0).child()
                if not user_name_view.exists(quick=True):
                    print(COLOR_OKGREEN + "Next item not found: probably reached end of the screen." + COLOR_ENDC)
                    break

                username = user_name_view.get_text()
                screen_iterated_followers.append(username)
                scroll_end_detector.notify_username_iterated(username)

                if storage.is_user_in_blacklist(username):
                    print("@" + username + " is in blacklist. Skip.")
                elif is_myself and storage.check_user_was_interacted(username):
                    print("@" + username + ": already interacted. Skip.")
                    screen_skipped_followers_count += 1
                elif is_myself and storage.check_user_was_interacted_recently(username):
                    print("@" + username + ": already interacted in the last week. Skip.")
                    screen_skipped_followers_count += 1
                else:
                    print("@" + username + ": interact")
                    user_name_view.click()

                    can_follow = not is_myself \
                        and not is_follow_limit_reached() \
                        and storage.get_following_status(username) == FollowingStatus.NONE

                    interaction_succeed, followed = interaction(device, username=username, can_follow=can_follow)
                    storage.add_interacted_user(username, followed=followed)
                    can_continue = on_interaction(succeed=interaction_succeed,
                                                  followed=followed)

                    if not can_continue:
                        return

                    print("Back to followers list")
                    device.back()
        except IndexError:
            print(COLOR_FAIL + "Cannot get next item: probably reached end of the screen." + COLOR_ENDC)

        if is_myself and scrolled_to_top():
            print(COLOR_OKGREEN + "Scrolled to top, finish." + COLOR_ENDC)
            return
        elif len(screen_iterated_followers) > 0:
            load_more_button = device.find(resourceId='com.instagram.android:id/row_load_more_button')
            load_more_button_exists = load_more_button.exists(quick=True)

            if scroll_end_detector.is_the_end():
                return

            need_swipe = screen_skipped_followers_count == len(screen_iterated_followers)
            list_view = device.find(resourceId='android:id/list',
                                    className='android.widget.ListView')
            if not list_view.exists():
                print(COLOR_FAIL + "Cannot find the list of followers. Trying to press back again." + COLOR_ENDC)
                device.back()
                list_view = device.find(resourceId='android:id/list',
                                        className='android.widget.ListView')

            if is_myself:
                print(COLOR_OKGREEN + "Need to scroll now" + COLOR_ENDC)
                list_view.scroll(DeviceFacade.Direction.TOP)
            else:
                pressed_retry = False
                if load_more_button_exists:
                    retry_button = load_more_button.child(className='android.widget.ImageView')
                    if retry_button.exists():
                        print("Press \"Load\" button")
                        retry_button.click()
                        random_sleep()
                        pressed_retry = True

                if need_swipe and not pressed_retry:
                    print(COLOR_OKGREEN + "All followers skipped, let's do a swipe" + COLOR_ENDC)
                    list_view.swipe(DeviceFacade.Direction.BOTTOM)
                else:
                    print(COLOR_OKGREEN + "Need to scroll now" + COLOR_ENDC)
                    list_view.scroll(DeviceFacade.Direction.BOTTOM)
        else:
            print(COLOR_OKGREEN + "No followers were iterated, finish." + COLOR_ENDC)
            return



def _iterate_over_comments(device, interaction, is_follow_limit_reached, storage, on_interaction, is_myself):
	# Wait until list is rendered
	# device.find(resourceId='com.instagram.android:id/follow_list_container',
	#             className='android.widget.LinearLayout').wait()

	# def scrolled_to_top():
	#     row_search = device.find(resourceId='com.instagram.android:id/row_search_edit_text',
	#                              className='android.widget.EditText')
	#     return row_search.exists()

	# prev_screen_iterated_followers = []
	# while True:
	#     print("Iterate over visible followers")
	#     random_sleep()
	    # screen_iterated_followers = []
	    # screen_skipped_followers_count = 0

	#     try:
	#         for item in device.find(resourceId='com.instagram.android:id/follow_list_container',
	#                                 className='android.widget.LinearLayout'):
	#             user_info_view = item.child(index=1)
	#             user_name_view = user_info_view.child(index=0).child()
	#             if not user_name_view.exists(quick=True):
	#                 print(COLOR_OKGREEN + "Next item not found: probably reached end of the screen." + COLOR_ENDC)
	#                 break
	#             #get user từ comment    
					

	#             # lấy username từ Followers
	#             username = user_name_view.get_text()
	#             screen_iterated_followers.append(username)

	            # if not is_myself and storage.check_user_was_interacted(username):
	            #     print("@" + username + ": already interacted. Skip.")
	            #     screen_skipped_followers_count += 1
	            # elif is_myself and storage.check_user_was_interacted_recently(username):
	            #     print("@" + username + ": already interacted in the last week. Skip.")
	            #     screen_skipped_followers_count += 1
	            # else:
					
	#                 print("@" + username + ": interact")
	#                 # Nhảy vào username vào tương tác
	#                 user_name_view.click()
	#                 # Kiểm tra có Follow được k
  
				  #   can_follow = not is_myself \
				  #       and not is_follow_limit_reached() \
				  #       and storage.get_following_status(username) == FollowingStatus.NONE

				  #   interaction_succeed, followed = interaction(device, username=username, can_follow=can_follow)
				  #   storage.add_interacted_user(username, followed=followed)
				  #   can_continue = on_interaction(succeed=interaction_succeed,
				  #                                 followed=followed)

				  #   if not can_continue:
				  #       return

				  #   print("Back to followers list")
				  #   device.back()
	#     except IndexError:
	#         print(COLOR_FAIL + "Cannot get next item: probably reached end of the screen." + COLOR_ENDC)

	#     if is_myself and scrolled_to_top():
	#         print(COLOR_OKGREEN + "Scrolled to top, finish." + COLOR_ENDC)
	#         return
	#     elif len(screen_iterated_followers) > 0:
	#         load_more_button = device.find(resourceId='com.instagram.android:id/row_load_more_button')
	#         load_more_button_exists = load_more_button.exists()

	#         if not load_more_button_exists and screen_iterated_followers == prev_screen_iterated_followers:
	#             print(COLOR_OKGREEN + "Iterated exactly the same followers twice, finish." + COLOR_ENDC)
	#             return

	#         need_swipe = screen_skipped_followers_count == len(screen_iterated_followers)
	#         list_view = device.find(resourceId='android:id/list',
	#                                 className='android.widget.ListView')
	#         if is_myself:
	#             print(COLOR_OKGREEN + "Need to scroll now" + COLOR_ENDC)
	#             list_view.scroll(DeviceFacade.Direction.TOP)
	#         else:
	#             pressed_retry = False
	#             if load_more_button_exists:
	#                 retry_button = load_more_button.child(className='android.widget.ImageView')
	#                 if retry_button.exists():
	#                     retry_button.click()
	#                     random_sleep()
	#                     pressed_retry = True

	#             if need_swipe and not pressed_retry:
	#                 print(COLOR_OKGREEN + "All followers skipped, let's do a swipe" + COLOR_ENDC)
	#                 list_view.swipe(DeviceFacade.Direction.BOTTOM)
	#             else:
	#                 print(COLOR_OKGREEN + "Need to scroll now" + COLOR_ENDC)
	#                 list_view.scroll(DeviceFacade.Direction.BOTTOM)

	#         prev_screen_iterated_followers.clear()
	#         prev_screen_iterated_followers += screen_iterated_followers
	#     else:
	#         print(COLOR_OKGREEN + "No followers were iterated, finish." + COLOR_ENDC)
	#         return

	screen_iterated_followers = []
	screen_skipped_followers_count = 0
	time.sleep(2)
	device.back()
	limit_count_open_photo = 10 # Số lần mở photo bị fail
	count = 0
	random_sleep()
	DeviceFacade.mini_swipe(device, 0.5)
	random_sleep()
	
	photo_interacted  = []

	while True:
		
		row = random.randint(0, 3)
		col = random.randint(0, 2)
		pixel =  str(row) +  str(col)

		if pixel not in photo_interacted:
			photo_opened = open_photo_from_profile(device, interaction, is_follow_limit_reached, storage, on_interaction, is_myself, count, row, col)
		else:
			print(yellow + "[*] Photo interacted, Skipped" +  end)
			continue

		if count == limit_count_open_photo:
			print(yellow + "[+] Đã mở quá nhiều ảnh, giới hạn 1 session chỉ nên 10 tấm" + end)
			break
		
		
		if photo_opened == True:

			try:
				print(blue + "[*] Try to open photo" + end)
				random_sleep()

				print(blue + "[+] Light Swipe this images" + end)
				DeviceFacade.mini_swipe(device, 0.2)

				random_sleep()
				has_comment = click_view_all_comment(device)
				if has_comment:
					print(blue + "[*] Photo Opened" + end)
					like_users_comment(device, interaction, is_follow_limit_reached, storage, on_interaction, is_myself)
				else:
					print(red + "[*] No comment found, maybe try scroll or press back" + end)
					random_sleep()					
					back_to_mainpage(device)
					# DeviceFacade.mini_swipe(device)
					# device.back()
				count = count + 1
				print(yellow + "[+] Interacted success " + str(count) + " Photo at Pixel " + pixel + end)
			except Exception as e:
				print(e)
				print(red + "[*] Error, mở ảnh nhưng không lấy được comment" + end)
				back_to_mainpage(device)
				continue
			# Mở rồi thì phải đóng chứ, đm ngu vãi lol
			# Tự động trở về main page rồi
			# device.back()
			
			random_sleep()
		else:
			print(red + "[*] Mở ảnh đéo được rồi, lại nhé" + end)
			# coordinator_layout = device.find(resourceId='com.instagram.android:id/coordinator_root_layout')
			# if coordinator_layout.exists():
			# 	print("Scroll down to see more photos.")
			# 	coordinator_layout.scroll(DeviceFacade.Direction.BOTTOM)
			continue
		back_to_mainpage(device)

	print(blue + "[*] Session Done" + end)
	# Kiểm tra xem có phải đang ở phần comment không thì back về trang chủ
	back_to_mainpage(device)
	time.sleep(10)



def open_photo_from_profile(device, interaction, is_follow_limit_reached, storage, on_interaction, is_myself, count, row, col):

	# get photo of row 1 tao ngau nhien bang ham random
	# if count == 0:
	# 	row = 0
	# 	column = 0
	# elif count == 1:
	# 	row = 0
	# 	column = 1
	# else:
	# 	row = random.randint(0, 2)
	# 	column =  random.randint(0, 2)

	row = row
	column = col

	print(blue + "[*] Open image at:" + str(row) + " " + str(column) +  end)
	
	try:
		recycler_view = device.find(resourceId='android:id/list')
		row_view = recycler_view.child(index=row + 1)
		if not row_view.exists():
			return False
		item_view = row_view.child(index=column)
		if not item_view.exists():
			return False
		random_sleep()
		item_view.click()
		time.sleep(2)
		return True
		# Open Photo
	except Exception as e:
		print(red + "[*] Open Photo In Post Error" + end)
		return False


def like_users_comment(device, interaction, is_follow_limit_reached, storage, on_interaction, is_myself):
	
	screen_iterated_followers = []
	screen_skipped_followers_count = 0
	total = ['wood_sneaker', 'chickenflyy__', 'bear.sneaker', 'leostore.top_', 'mangoo.sneaker']
	flag = []
	old_flag = []
	followed_list = []
	limit = 10
	i = 0

	while True:
		try:
			# random_sleep()
			flag = []
			row_comment_container = device.find(resourceId="com.instagram.android:id/row_comment_container", className='android.widget.LinearLayout')
			if row_comment_container.exists():
				for item in row_comment_container:

					#Kiểm tra xem có bị click vào comement hoặc reply ko?
					check_state_comment(device)
					random_sleep()
					raw_comment = item.child(index=0).child(index=1).child(index=0)
					text_comment = raw_comment.get_text()

					if text_comment.strip() != "":
						username = text_comment.split(" ")[0]
						flag.append(str(username))
						print(flag)

						if (username in total) or (len(username) == 2):
							print(blue + "[*] User interacted, Skipped" + end)
							continue
						else:
							total.append(username)

						# if len(username) == 2:
						# 	#Trường hợp lấy nhầm cmnr DOM, đéo ra tên username mà ra 1d, 1ww
						# 	continue

						print("Interact @" + username)
						user_interact = item.child(index=0).child(index=1).child(index=0).child(index=0)

						if user_interact.exists():
							# kiem tra xem user co trong Storage
							if not is_myself and storage.check_user_was_interacted(username):
								print("@" + username + ": already interacted. Skip.")
								screen_skipped_followers_count += 1
								continue

							elif is_myself and storage.check_user_was_interacted_recently(username):
								print("@" + username + ": already interacted in the last week. Skip.")
								screen_skipped_followers_count += 1
								continue

							try:
								user_interact.click()
							#wait to load
								time.sleep(2)
							except Exception as e:
								print(red + "[*] Click to user Error, change user" + end)
								continue
							# Lấy số bài post, tránh mấy con đĩ clone acc
							post_count = get_post_count(device)

							# Tài khoản bị khoá
							if post_count == None:
								device.back()
								continue

							print(blue + "User @" + username + " has: " + str(post_count) + " post" + end)
							
							if int(post_count) > 3:
								# Gọi hàm tương tác chính nè mấy con chó
								can_follow = not is_myself \
									and not is_follow_limit_reached() \
									and storage.get_following_status(username) == FollowingStatus.NONE

								interaction_succeed, followed = interaction(device, username=username, can_follow=can_follow)
								storage.add_interacted_user(username, followed=followed)
								can_continue = on_interaction(succeed=interaction_succeed,
															followed=followed)
								if not can_continue:
									return

								# if followed:
								# 	print("Follow xong rồi nhé mấy bợn ơi")

								device.back()
							else:
								random_sleep()	
								device.back()


			print(flag)
			print("*" * 30)
			print(old_flag)
			if flag == old_flag:
				print(yellow + "[*] End of page" +  end)
				back_to_mainpage(device)
				return True

			old_flag = flag
			random_sleep()
			print("Tao swipe nhé, hết mẹ nó page rồi")
			list_view = device.find(resourceId='android:id/list', className='android.widget.ListView')
			# list_view.swipe(DeviceFacade.Direction.BOTTOM)
			if list_view.exists():
				list_view.scroll(DeviceFacade.Direction.BOTTOM)
				time.sleep(1)
			else:
				print("Không tìm thấy view để scroll")
			# Đề phòng nếu bị sao đó lỗi, cứ đúng 7 lần là sút thôi
			i = i + 1
			if i == limit:
				print("Xong 3 trang thôi nhé, ngưng.")
				back_to_mainpage(device)
				return True

		except Exception as e:
			print("Error 1: " + str(e))
			print("Lỗi ở đây rồi, có thể đéo lấy được số bài post, quay về nhé")
			# Trở về main page
			back_to_mainpage(device)
			print(yellow + "[*] Quay về trang chủ " + end)
			return False


def click_view_all_comment(device):
	try:
		btn_view_all_comment = device.find(resourceId="com.instagram.android:id/row_feed_view_all_comments_text")
		if btn_view_all_comment.exists():
			print(blue + "[*] Click to view all comments" + end)
			btn_view_all_comment.click()
			return True
		else:
			print(red + "[*] Can't find view all comments" +  end)
			return False
	except Exception as e:
		return False

def get_post_count(device):
	post = None
	try:
		post_view = device.find(resourceId="com.instagram.android:id/row_profile_header_textview_post_count")
		if post_view.exists():
			post = post_view.get_text()
			return int(post.replace(",",""))
	except Exception as e:
		# print("Get post count error " + str(e))
		print(red + "[*] Can't get number of posts " + end)
		return None

def check_state_comment(device):
	try:
		if device.find(resourceId="com.instagram.android:id/action_bar_textview_title").exists():
			check_state = device.find(resourceId="com.instagram.android:id/action_bar_textview_title")
		elif device.find(resourceId="com.instagram.android:id/action_bar_title").exists():
			check_state = device.find(resourceId="com.instagram.android:id/action_bar_title")
		else:
			print(red + "[*] Can't get element of text bar" + end)
			return

		if check_state.get_text() == "1 Selected":
			print(red + "[Error] Comment selected, Press Back")
			device.back()
			return False
		elif check_state.get_text() == "Comments":
			print(blue + "[*] Đang ở trang Comments " + end)
			return True
	except Exception as e:
		print(red + "[+] Can't get state"  + end)
		pass
	
def check_state_reply(device):

	check_reply = device.find(resourceId="com.instagram.android:id/layout_comment_composer_callout")
	print(check_reply.get_text())
	if check_reply.exists():
		print(red + "[Error] Comment Reply, press back" + end)
		device.back()
		return False
	elif check_reply.get_text() == "Comments":
		print(blue + "[*] Đang ở trang Comments" + end)
		return True

def back_to_mainpage(device):

	try:
		if device.find(resourceId="com.instagram.android:id/action_bar_textview_title").exists():
			check_state = device.find(resourceId="com.instagram.android:id/action_bar_textview_title")
		elif device.find(resourceId="com.instagram.android:id/action_bar_title").exists():
			check_state = device.find(resourceId="com.instagram.android:id/action_bar_title")
		else:
			print(red + "[*] Can't get element of text bar" + end)
			return

		if check_state.get_text() == "Posts":
			print(yellow + "[+] Từ Post Page về Mainpage" + end)
			device.back()
			
		if check_state.get_text() == "Comments":
			print(yellow + "[+] Từ Comments Page về Mainpage" + end)
			device.back()
			random_sleep()
			device.back()
	except Exception as e:
		print(red + "[*] Không tìm thấy layout, do hình ko đúng tiêu chuẩn" + end)
		device.back()
		pass